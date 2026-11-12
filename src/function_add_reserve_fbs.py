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


async def reserve_fbs(
    db: AsyncSession, product_id: int, warehouse_id: int, qty: int
) -> None:
    """
    Создаёт резерв FBS на выбранном складе фулфилмента (ФФ), блокируя доступный остаток
    до отправки заказа клиенту или отмены.

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        product_id: int - Идентификатор товара (артикула).
        warehouse_id: int - Идентификатор склада-отправителя (ФФ).
        qty: int - Количество единиц товара для резервирования.

    Returns:
        None

    Raises:
        HTTPException (400) - Некорректные параметры, склад удалён, товар на складе закончился (0 шт.)
            или на выбранном ФФ не хватает доступного товара (с указанием общего остатка
            на других активных складах при его наличии).
        HTTPException (404) - Товар или склад не найдены.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "reserve_fbs: старт резервирования (product_id=%s, warehouse_id=%s, qty=%s)",
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
                "reserve_fbs: некорректные параметры (product_id=%s, warehouse_id=%s, qty=%s)",
                product_id,
                warehouse_id,
                qty,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Переданы некорректные параметры для резерва FBS.",
            )

        check_product = await db.execute(
            select(Products).where(Products.id == product_id)
        )
        if not check_product.scalar_one_or_none():
            main_log.warning(
                "reserve_fbs: товар не найден (product_id=%s)", product_id
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
                "reserve_fbs: склад не найден (warehouse_id=%s)", warehouse_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Склад не найден.",
            )
        if warehouse.is_deleted:
            main_log.warning(
                "reserve_fbs: попытка резерва на удалённом складе (warehouse_id=%s, name='%s')",
                warehouse_id,
                warehouse.name,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Невозможно создать резерв на удалённом складе.",
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
                "reserve_fbs: нехватка товара (product_id=%s, warehouse_id=%s, name='%s', available=%s, requested=%s, total_available=%s)",
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

        stock_item.qty_reserved_fbs += qty

        new_movement = Movement(
            product_id=product_id,
            qty=qty,
            movement_type="FBS",
            from_warehouse_id=warehouse_id,
            to_warehouse_id=None,
            status="RESERVED",
        )
        db.add(new_movement)
        await db.commit()

        main_log.info(
            "reserve_fbs: резерв успешно создан (product_id=%s, warehouse_id=%s, qty=%s, new_reserved=%s)",
            product_id,
            warehouse_id,
            qty,
            stock_item.qty_reserved_fbs,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "reserve_fbs: ошибка БД (product_id=%s, warehouse_id=%s, qty=%s)",
            product_id,
            warehouse_id,
            qty,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
