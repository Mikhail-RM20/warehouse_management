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


async def delete_warehouse(db: AsyncSession, warehouse_id: int) -> None:
    """
    Выполняет мягкое удаление склада фулфилмента (ФФ), устанавливая флаг is_deleted = True,
    с сохранением всех числящихся остатков и истории операций.

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        warehouse_id: int - ID склада для удаления.

    Returns:
        None

    Raises:
        HTTPException (400) - Не передан корректный ID склада или склад уже удалён.
        HTTPException (404) - Склад не найден.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "delete_warehouse: старт удаления склада (warehouse_id=%s)",
        warehouse_id,
    )

    try:
        if not warehouse_id or warehouse_id <= 0:
            main_log.warning(
                "delete_warehouse: некорректный ID склада (warehouse_id=%s)",
                warehouse_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не передан корректный идентификатор склада.",
            )
        check_warehouse = await db.execute(
            select(Warehouse).where(Warehouse.id == warehouse_id)
        )
        result_check = check_warehouse.scalar_one_or_none()
        if not result_check:
            main_log.warning(
                "delete_warehouse: склад не найден (warehouse_id=%s)",
                warehouse_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Склад не найден.",
            )
        if result_check.is_deleted:
            main_log.warning(
                "delete_warehouse: склад уже удалён (warehouse_id=%s, name='%s')",
                warehouse_id,
                result_check.name,
            )
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Склад уже удален.",
            )

        warehouse_name = result_check.name
        result_check.is_deleted = True
        await db.commit()

        main_log.info(
            "delete_warehouse: склад успешно удалён (warehouse_id=%s, name='%s')",
            warehouse_id,
            warehouse_name,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "delete_warehouse: ошибка БД при удалении склада (warehouse_id=%s)",
            warehouse_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
