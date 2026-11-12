import logging.config

from core import dict_config
from database import Warehouse
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("services_logger")
main_log.setLevel(logging.DEBUG)


async def add_warehouse(db: AsyncSession, name_warehouse: str) -> None:
    """
    Создаёт новый склад фулфилмента (ФФ) в базе данных.

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        name_warehouse: str - Название нового склада.

    Returns:
        None

    Raises:
        HTTPException (409) - Склад с таким названием уже существует.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "add_warehouse: старт создания склада (name='%s')", name_warehouse
    )

    try:
        check_warehouse = await db.execute(
            select(Warehouse).where(Warehouse.name == name_warehouse)
        )
        result_check = check_warehouse.scalar_one_or_none()
        if result_check is not None:
            main_log.warning(
                "add_warehouse: склад с таким названием уже существует (name='%s')",
                name_warehouse,
            )
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Склад с таким названием уже есть.",
            )
        new_warehouse = Warehouse(name=name_warehouse)
        db.add(new_warehouse)
        await db.commit()

        main_log.info(
            "add_warehouse: склад успешно создан (name='%s', id=%s)",
            name_warehouse,
            new_warehouse.id,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "add_warehouse: ошибка БД при создании склада (name='%s')",
            name_warehouse,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
