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


async def cancel_fbs(db: AsyncSession, movement_id: int) -> None:
    """
    Отменяет активный резерв FBS, освобождая заблокированный остаток товара на складе.

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        movement_id: int - ID записи движения (заказа FBS) из URL.

    Returns:
        None

    Raises:
        HTTPException (400) - Некорректный ID заказа FBS или резерв уже отправлен/отменён.
        HTTPException (404) - Заказ FBS не найден.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "cancel_fbs: старт отмены резерва (movement_id=%s)", movement_id
    )

    try:
        if not movement_id or movement_id <= 0:
            main_log.warning(
                "cancel_fbs: некорректный ID заказа (movement_id=%s)",
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
                "cancel_fbs: заказ FBS не найден (movement_id=%s)", movement_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заказ FBS не найден.",
            )
        if movement.status != "RESERVED":
            main_log.warning(
                "cancel_fbs: попытка отменить неактивный резерв (movement_id=%s, status=%s)",
                movement_id,
                movement.status,
            )
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Можно отменить только активный резерв FBS.",
            )

        check_stock = await db.execute(
            select(StockItem)
            .where(
                StockItem.product_id == movement.product_id,
                StockItem.warehouse_id == movement.from_warehouse_id,
            )
            .with_for_update()
        )
        stock_item = check_stock.scalar_one_or_none()
        if stock_item and stock_item.qty_reserved_fbs >= movement.qty:
            stock_item.qty_reserved_fbs -= movement.qty

        movement.status = "CANCELLED"
        await db.commit()

        main_log.info(
            "cancel_fbs: резерв успешно отменён (movement_id=%s, product_id=%s, warehouse_id=%s, qty=%s)",
            movement_id,
            movement.product_id,
            movement.from_warehouse_id,
            movement.qty,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "cancel_fbs: ошибка БД при отмене резерва (movement_id=%s)",
            movement_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
