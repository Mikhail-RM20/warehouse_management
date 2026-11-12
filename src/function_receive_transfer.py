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


async def receive_transfer(db: AsyncSession, movement_id: int) -> None:
    """
    Подтверждает приёмку перемещения товара на складе-получателе (ФФ), увеличивая его физический остаток
    и завершая движение.

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        movement_id: int - ID записи движения (перемещения между ФФ) из URL.

    Returns:
        None

    Raises:
        HTTPException (400) - Не передан корректный ID перемещения или перемещение уже принято/отменено.
        HTTPException (404) - Перемещение не найдено.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "receive_transfer: старт приёмки перемещения (movement_id=%s)",
        movement_id,
    )

    try:
        if not movement_id or movement_id <= 0:
            main_log.warning(
                "receive_transfer: некорректный ID перемещения (movement_id=%s)",
                movement_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не передан корректный идентификатор перемещения.",
            )

        check_movement = await db.execute(
            select(Movement)
            .where(Movement.id == movement_id)
            .with_for_update()
        )
        movement = check_movement.scalar_one_or_none()

        if not movement or movement.movement_type != "TRANSFER":
            main_log.warning(
                "receive_transfer: перемещение не найдено (movement_id=%s)",
                movement_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Перемещение не найдено.",
            )

        if movement.status != "IN_TRANSIT":
            main_log.warning(
                "receive_transfer: перемещение уже принято или отменено (movement_id=%s, status=%s)",
                movement_id,
                movement.status,
            )
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Перемещение уже принято или отменено.",
            )

        check_stock = await db.execute(
            select(StockItem)
            .where(
                StockItem.product_id == movement.product_id,
                StockItem.warehouse_id == movement.to_warehouse_id,
            )
            .with_for_update()
        )
        stock_item = check_stock.scalar_one_or_none()

        if stock_item:
            stock_item.qty_on_hand += movement.qty
        else:
            stock_item = StockItem(
                product_id=movement.product_id,
                warehouse_id=movement.to_warehouse_id,
                qty_on_hand=movement.qty,
                qty_reserved_fbs=0,
            )
            db.add(stock_item)

        movement.status = "COMPLETED"
        await db.commit()

        main_log.info(
            "receive_transfer: перемещение успешно принято (movement_id=%s, product_id=%s, to_warehouse_id=%s, qty=%s, new_on_hand=%s)",
            movement_id,
            movement.product_id,
            movement.to_warehouse_id,
            movement.qty,
            stock_item.qty_on_hand,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "receive_transfer: ошибка БД при приёмке перемещения (movement_id=%s)",
            movement_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
