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


async def rename_warehouse(
    db: AsyncSession, warehouse_id: int, warehouse_name: str
) -> None:
    """
    Переименовывает существующий активный склад фулфилмента (ФФ).

    Args:
        db: AsyncSession - Асинхронная сессия БД.
        warehouse_id: int - ID склада для переименования.
        warehouse_name: str - Новое название склада.

    Returns:
        None

    Raises:
        HTTPException (400) - Не передан корректный ID склада, пустое название или склад удалён.
        HTTPException (404) - Склад не найден.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "rename_warehouse: старт переименования склада (warehouse_id=%s, new_name='%s')",
        warehouse_id,
        warehouse_name,
    )

    try:
        if not warehouse_id or warehouse_id <= 0:
            main_log.warning(
                "rename_warehouse: некорректный ID склада (warehouse_id=%s)",
                warehouse_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не передан корректный идентификатор склада.",
            )
        if not warehouse_name:
            main_log.warning(
                "rename_warehouse: передано пустое название склада (warehouse_id=%s)",
                warehouse_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не передан параметр для изменения названия склада.",
            )
        check_warehouse = await db.execute(
            select(Warehouse).where(Warehouse.id == warehouse_id)
        )
        result_check = check_warehouse.scalar_one_or_none()
        if not result_check:
            main_log.warning(
                "rename_warehouse: склад не найден (warehouse_id=%s)",
                warehouse_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Склад не найден.",
            )
        if result_check.is_deleted:
            main_log.warning(
                "rename_warehouse: попытка переименовать удалённый склад (warehouse_id=%s, current_name='%s')",
                warehouse_id,
                result_check.name,
            )
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя переименовать удаленный склад.",
            )

        old_name = result_check.name
        result_check.name = warehouse_name
        await db.commit()

        main_log.info(
            "rename_warehouse: склад успешно переименован (warehouse_id=%s, old_name='%s', new_name='%s')",
            warehouse_id,
            old_name,
            warehouse_name,
        )

    except SQLAlchemyError:
        await db.rollback()
        main_log.exception(
            "rename_warehouse: ошибка БД при переименовании склада (warehouse_id=%s, new_name='%s')",
            warehouse_id,
            warehouse_name,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка БД.",
        )
