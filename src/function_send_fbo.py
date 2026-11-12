import logging.config

from core import dict_config
from database import Movement, Products, StockItem, Warehouse
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("services_logger")
main_log.setLevel(logging.DEBUG)


async def send_fbo(
    db: AsyncSession, product_id: int, warehouse_id: int, qty: int
) -> None:
    """
    Оформляет отправку поставки FBO со склада фулфилмента (ФФ) на склад маркетплейса,
    списывая физический остаток и переводя движение в статус «в пути».

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        product_id: int — идентификатор товара (артикула).
        warehouse_id: int — идентификатор склада-отправителя (ФФ).
        qty: int — количество единиц товара для отправки.

    Returns:
        None

    Raises:
        HTTPException (400) — некорректные параметры, склад удалён, товар на складе закончился (0 шт.)
            или на выбранном ФФ не хватает доступного товара (с указанием общего остатка
            на других активных складах при его наличии).
        HTTPException (404) — товар или склад не найдены.
        HTTPException (500) — внутренняя ошибка БД.
    """
    main_log.info(
        "send_fbo: старт отправки поставки FBO (product_id=%s, warehouse_id=%s, qty=%s)",
        product_id,
        warehouse_id,
        qty,
    )

    try:
        if (
            not product_id
            or product_id <= 0
            or not warehouse_id
            or warehouse_id <= 0
            or qty <= 0
        ):
            main_log.warning(
                "send_fbo: некорректные параметры (product_id=%s, warehouse_id=%s, qty=%s)",
                product_id,
                warehouse_id,
                qty,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Переданы некорректные параметры для отправки FBO.",
            )

        check_product = await db.execute(
            select(Products).where(Products.id == product_id)
        )
        if not check_product.scalar_one_or_none():
            main_log.warning(
                "send_fbo: товар не найден (product_id=%s)", product_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Товар не найден.",
            )

        check_wh = await db.execute(
            select(Warehouse).where(Warehouse.id == warehouse_id)
        )
        warehouse = check_wh.scalar_one_or_none()
        if not warehouse:
            main_log.warning(
                "send_fbo: склад не найден (warehouse_id=%s)", warehouse_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Склад не найден.",
            )
        if warehouse.is_deleted:
            main_log.warning(
                "send_fbo: попытка отправки FBO с удалённого склада (warehouse_id=%s, name='%s')",
                warehouse_id,
                warehouse.name,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя отправить FBO с удалённого склада.",
            )

        warehouse_name = warehouse.name

        check_stock = await db.execute(
            select(StockItem)
            .where(
                StockItem.product_id == product_id,
                StockItem.warehouse_id == warehouse_id,
            )
            .with_for_update()
        )
        stock_item = check_stock.scalar_one_or_none()
        available = (
            (stock_item.qty_on_hand - stock_item.qty_reserved_fbs)
            if stock_item
            else 0
        )

        if not stock_item or available < qty:
            total_res = await db.execute(
                select(
                    func.sum(
                        StockItem.qty_on_hand - StockItem.qty_reserved_fbs
                    )
                )
                .join(Warehouse, Warehouse.id == StockItem.warehouse_id)
                .where(
                    StockItem.product_id == product_id,
                    Warehouse.is_deleted.is_(False),
                )
            )
            total_available = int(total_res.scalar_one() or 0)

            main_log.warning(
                "send_fbo: нехватка товара (product_id=%s, warehouse_id=%s, name='%s', available=%s, requested=%s, total_available=%s)",
                product_id,
                warehouse_id,
                warehouse_name,
                available,
                qty,
                total_available,
            )

            if available <= 0:
                if total_available >= qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"На складе «{warehouse_name}» товар закончился (доступно: 0 шт.), "
                            f"но общий остаток на других складах: {total_available} шт."
                        ),
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"На складе «{warehouse_name}» товар закончился (доступно: 0 шт.).",
                )

            if total_available >= qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"На складе «{warehouse_name}» недостаточно товара (доступно: {available} шт., "
                        f"запрошено: {qty} шт.), но общий остаток на других складах: {total_available} шт."
                    ),
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно товара на складе «{warehouse_name}» (доступно: {available} шт.).",
            )

        stock_item.qty_on_hand -= qty

        new_movement = Movement(
            product_id=product_id,
            qty=qty,
            movement_type="FBO",
            from_warehouse_id=warehouse_id,
            to_warehouse_id=None,
            status="IN_TRANSIT",
        )
        db.add(new_movement)
        await db.commit()

        main_log.info(
            "send_fbo: поставка FBO успешно отправлена (product_id=%s, warehouse_id=%s, qty=%s, new_on_hand=%s)",
            product_id,
            warehouse_id,
            qty,
            stock_item.qty_on_hand,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "send_fbo: ошибка БД при отправке поставки FBO (product_id=%s, warehouse_id=%s, qty=%s)",
            product_id,
            warehouse_id,
            qty,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
