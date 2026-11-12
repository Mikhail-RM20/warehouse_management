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


async def send_transfer(
    db: AsyncSession,
    product_id: int,
    from_warehouse_id: int,
    to_warehouse_id: int,
    qty: int,
) -> None:
    """
    Оформляет отправку перемещения товара со склада-отправителя на склад-получатель,
    списывая физический остаток со склада отправления и переводя движение в статус «в пути».

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        product_id: int — идентификатор товара (артикула).
        from_warehouse_id: int — идентификатор склада-отправителя.
        to_warehouse_id: int — идентификатор склада-получателя.
        qty: int — количество единиц товара для перемещения.

    Returns:
        None

    Raises:
        HTTPException (400) — склады отправления и получения совпадают, один из складов
            удалён, товар на складе-отправителе закончился (0 шт.) либо на складе-отправителе
            не хватает доступного товара (с указанием общего остатка на других активных
            складах при его наличии).
        HTTPException (404) — товар или один из складов не найдены.
        HTTPException (500) — внутренняя ошибка БД.
    """
    main_log.info(
        "send_transfer: старт отправки перемещения (product_id=%s, from_warehouse_id=%s, to_warehouse_id=%s, qty=%s)",
        product_id,
        from_warehouse_id,
        to_warehouse_id,
        qty,
    )

    try:
        if from_warehouse_id == to_warehouse_id:
            main_log.warning(
                "send_transfer: совпадают склады отправления и получения (warehouse_id=%s)",
                from_warehouse_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Склад-отправитель и склад-получатель не могут совпадать.",
            )

        check_product = await db.execute(
            select(Products).where(Products.id == product_id)
        )
        if not check_product.scalar_one_or_none():
            main_log.warning(
                "send_transfer: товар не найден (product_id=%s)", product_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Товар не найден.",
            )

        from_wh_res = await db.execute(
            select(Warehouse).where(Warehouse.id == from_warehouse_id)
        )
        from_wh = from_wh_res.scalar_one_or_none()

        to_wh_res = await db.execute(
            select(Warehouse).where(Warehouse.id == to_warehouse_id)
        )
        to_wh = to_wh_res.scalar_one_or_none()

        if not from_wh or not to_wh:
            main_log.warning(
                "send_transfer: один из складов не найден (from_warehouse_id=%s, to_warehouse_id=%s)",
                from_warehouse_id,
                to_warehouse_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Один из складов не найден.",
            )
        if from_wh.is_deleted or to_wh.is_deleted:
            main_log.warning(
                "send_transfer: попытка перемещения с/на удалённый склад (from_id=%s, from_deleted=%s, to_id=%s, to_deleted=%s)",
                from_warehouse_id,
                from_wh.is_deleted,
                to_warehouse_id,
                to_wh.is_deleted,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя перемещать товар с удаленного или на удаленный склад.",
            )

        from_wh_name = from_wh.name

        check_stock = await db.execute(
            select(StockItem)
            .where(
                StockItem.product_id == product_id,
                StockItem.warehouse_id == from_warehouse_id,
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
                "send_transfer: нехватка товара (product_id=%s, from_warehouse_id=%s, name='%s', available=%s, requested=%s, total_available=%s)",
                product_id,
                from_warehouse_id,
                from_wh_name,
                available,
                qty,
                total_available,
            )

            if available <= 0:
                if total_available >= qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Товар на складе «{from_wh_name}» закончился (доступно: 0 шт.), "
                            f"но общий остаток на других складах: {total_available} шт."
                        ),
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Товар на складе «{from_wh_name}» закончился (доступно: 0 шт.).",
                )

            if total_available >= qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Недостаточно товара на складе «{from_wh_name}» (доступно: {available} шт., "
                        f"запрошено: {qty} шт.), но общий остаток на других складах: {total_available} шт."
                    ),
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно товара на складе «{from_wh_name}» (доступно: {available} шт.).",
            )

        stock_item.qty_on_hand -= qty

        new_movement = Movement(
            product_id=product_id,
            qty=qty,
            movement_type="TRANSFER",
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            status="IN_TRANSIT",
        )
        db.add(new_movement)
        await db.commit()

        main_log.info(
            "send_transfer: перемещение успешно отправлено (product_id=%s, from_warehouse_id=%s, to_warehouse_id=%s, qty=%s, new_on_hand=%s)",
            product_id,
            from_warehouse_id,
            to_warehouse_id,
            qty,
            stock_item.qty_on_hand,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "send_transfer: ошибка БД при отправке перемещения (product_id=%s, from_warehouse_id=%s, to_warehouse_id=%s, qty=%s)",
            product_id,
            from_warehouse_id,
            to_warehouse_id,
            qty,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
