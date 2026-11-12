import logging.config

from core import dict_config
from database import Movement, Products, StockItem, Warehouse
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("services_logger")
main_log.setLevel(logging.DEBUG)


async def add_inbound(
    db: AsyncSession, product_id: int, warehouse_id: int, qty: int
) -> None:
    """
    Оформляет приход товара на выбранный склад фулфилмента (ФФ) и фиксирует движение в истории.

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        product_id: int - ID товара (артикула).
        warehouse_id: int - ID склада-получателя (ФФ).
        qty: int - Количество единиц товара, поступающих на склад.

    Returns:
        None

    Raises:
        HTTPException (400) - Переданы некорректные параметры или попытка оформить приход на удалённый склад.
        HTTPException (404) - Товар или склад не найден.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "add_inbound: старт прихода (product_id=%s, warehouse_id=%s, qty=%s)",
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
                "add_inbound: некорректные параметры (product_id=%s, warehouse_id=%s, qty=%s)",
                product_id,
                warehouse_id,
                qty,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Переданы некорректные параметры для прихода.",
            )

        check_product = await db.execute(
            select(Products).where(Products.id == product_id)
        )
        if not check_product.scalar_one_or_none():
            main_log.warning(
                "add_inbound: товар не найден (product_id=%s)", product_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Товар не найден.",
            )

        check_warehouse = await db.execute(
            select(Warehouse).where(Warehouse.id == warehouse_id)
        )
        result_warehouse = check_warehouse.scalar_one_or_none()
        if not result_warehouse:
            main_log.warning(
                "add_inbound: склад не найден (warehouse_id=%s)", warehouse_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Склад не найден.",
            )
        if result_warehouse.is_deleted:
            main_log.warning(
                "add_inbound: попытка прихода на удалённый склад (warehouse_id=%s, name='%s')",
                warehouse_id,
                result_warehouse.name,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя оформить приход на удаленный склад.",
            )

        check_stock = await db.execute(
            select(StockItem)
            .where(
                StockItem.product_id == product_id,
                StockItem.warehouse_id == warehouse_id,
            )
            .with_for_update()
        )
        stock_item = check_stock.scalar_one_or_none()

        if stock_item:
            stock_item.qty_on_hand += qty
        else:
            stock_item = StockItem(
                product_id=product_id,
                warehouse_id=warehouse_id,
                qty_on_hand=qty,
                qty_reserved_fbs=0,
            )
            db.add(stock_item)

        new_movement = Movement(
            product_id=product_id,
            qty=qty,
            movement_type="INBOUND",
            from_warehouse_id=None,
            to_warehouse_id=warehouse_id,
            status="COMPLETED",
        )
        db.add(new_movement)
        await db.commit()

        main_log.info(
            "add_inbound: приход успешно оформлен (product_id=%s, warehouse_id=%s, qty=%s, new_on_hand=%s)",
            product_id,
            warehouse_id,
            qty,
            stock_item.qty_on_hand,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "add_inbound: ошибка БД (product_id=%s, warehouse_id=%s, qty=%s)",
            product_id,
            warehouse_id,
            qty,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
