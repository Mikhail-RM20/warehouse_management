import logging.config

from core import dict_config
from database import Movement, StockItem
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("services_logger")
main_log.setLevel(logging.DEBUG)


async def ship_fbs(db: AsyncSession, movement_id: int) -> None:
    """
    Подтверждает отправку зарезервированного заказа FBS клиенту, окончательно списывая
    товар с физического и зарезервированного остатка склада и переводя его в статус «в пути».

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        movement_id: int — идентификатор движения (заказа FBS) со статусом RESERVED.

    Returns:
        None

    Raises:
        HTTPException (400) — некорректный ID заказа, заказ уже отправлен или отменён,
            товар на складе закончился (0 шт.) либо фактического или зарезервированного
            остатка на складе недостаточно для отгрузки.
        HTTPException (404) — заказ FBS с указанным идентификатором не найден.
        HTTPException (500) — внутренняя ошибка БД.
    """
    main_log.info(
        "ship_fbs: старт отправки заказа FBS (movement_id=%s)", movement_id
    )

    try:
        if not movement_id or movement_id <= 0:
            main_log.warning(
                "ship_fbs: некорректный ID заказа (movement_id=%s)",
                movement_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный идентификатор заказа FBS.",
            )

        check_mov = await db.execute(
            select(Movement)
            .where(Movement.id == movement_id)
            .with_for_update()
        )
        movement = check_mov.scalar_one_or_none()

        if not movement or movement.movement_type != "FBS":
            main_log.warning(
                "ship_fbs: заказ FBS не найден (movement_id=%s)", movement_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заказ FBS не найден.",
            )

        mov_status = movement.status
        mov_qty = movement.qty
        mov_product_id = movement.product_id
        mov_warehouse_id = movement.from_warehouse_id

        if mov_status != "RESERVED":
            main_log.warning(
                "ship_fbs: заказ FBS уже отправлен или отменён (movement_id=%s, status=%s)",
                movement_id,
                mov_status,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Заказ FBS уже отправлен или отменён.",
            )

        check_stock = await db.execute(
            select(StockItem)
            .where(
                StockItem.product_id == mov_product_id,
                StockItem.warehouse_id == mov_warehouse_id,
            )
            .with_for_update()
        )
        stock_item = check_stock.scalar_one_or_none()

        if not stock_item or stock_item.qty_on_hand <= 0:
            main_log.warning(
                "ship_fbs: товар на складе закончился (movement_id=%s, product_id=%s, warehouse_id=%s)",
                movement_id,
                mov_product_id,
                mov_warehouse_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Товар на складе закончился, невозможно отправить заказ FBS.",
            )

        if (
            stock_item.qty_reserved_fbs < mov_qty
            or stock_item.qty_on_hand < mov_qty
        ):
            main_log.warning(
                "ship_fbs: недостаточно товара для отгрузки (movement_id=%s, product_id=%s, warehouse_id=%s, reserved=%s, on_hand=%s, required=%s)",
                movement_id,
                mov_product_id,
                mov_warehouse_id,
                stock_item.qty_reserved_fbs,
                stock_item.qty_on_hand,
                mov_qty,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Недостаточно товара для отправки заказа FBS "
                    f"(в резерве: {stock_item.qty_reserved_fbs} шт., на складе: {stock_item.qty_on_hand} шт., требуется: {mov_qty} шт.)."
                ),
            )

        stock_item.qty_reserved_fbs -= mov_qty
        stock_item.qty_on_hand -= mov_qty
        movement.status = "IN_TRANSIT"

        await db.commit()

        main_log.info(
            "ship_fbs: заказ FBS успешно отправлен (movement_id=%s, product_id=%s, warehouse_id=%s, qty=%s, new_on_hand=%s, new_reserved=%s)",
            movement_id,
            mov_product_id,
            mov_warehouse_id,
            mov_qty,
            stock_item.qty_on_hand,
            stock_item.qty_reserved_fbs,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "ship_fbs: ошибка БД при отправке заказа FBS (movement_id=%s)",
            movement_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
