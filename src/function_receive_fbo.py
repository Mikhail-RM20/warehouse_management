import logging.config

from core import dict_config
from database import Movement
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("services_logger")
main_log.setLevel(logging.DEBUG)


async def receive_fbo(db: AsyncSession, movement_id: int) -> None:
    """
    Подтверждает приёмку поставки FBO на складе маркетплейса, переводя движение из статуса «в пути» в завершённое.

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        movement_id: int - ID записи движения (поставки FBO) из URL.

    Returns:
        None

    Raises:
        HTTPException (400) - Некорректный ID поставки FBO или поставка уже принята/отменена.
        HTTPException (404) - Поставка FBO не найдена.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "receive_fbo: старт приёмки поставки FBO (movement_id=%s)", movement_id
    )

    try:
        if not movement_id or movement_id <= 0:
            main_log.warning(
                "receive_fbo: некорректный ID поставки (movement_id=%s)",
                movement_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный идентификатор поставки FBO.",
            )

        check_mov = await db.execute(
            select(Movement)
            .where(Movement.id == movement_id)
            .with_for_update()
        )
        movement = check_mov.scalar_one_or_none()

        if not movement or movement.movement_type != "FBO":
            main_log.warning(
                "receive_fbo: поставка FBO не найдена (movement_id=%s)",
                movement_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Поставка FBO не найдена.",
            )
        if movement.status != "IN_TRANSIT":
            main_log.warning(
                "receive_fbo: поставка FBO уже принята или отменена (movement_id=%s, status=%s)",
                movement_id,
                movement.status,
            )
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Поставка FBO уже принята или отменена.",
            )

        movement.status = "COMPLETED"
        await db.commit()

        main_log.info(
            "receive_fbo: поставка FBO успешно принята (movement_id=%s, product_id=%s, qty=%s)",
            movement_id,
            movement.product_id,
            movement.qty,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "receive_fbo: ошибка БД при приёмке поставки FBO (movement_id=%s)",
            movement_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
