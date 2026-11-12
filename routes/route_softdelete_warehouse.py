import logging.config

from core import dict_config
from database import get_db
from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src import delete_warehouse

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("route_logger")
main_log.setLevel(logging.DEBUG)

router = APIRouter()


@router.post(
    "/warehouse/delete/{warehouse_id}",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        303: {"description": "Редирект после удаления"},
        400: {
            "description": "Не передан корректный ID склада или склад уже удален"
        },
        404: {"description": "Склад не найден"},
        500: {"description": "Ошибка БД"},
    },
    include_in_schema=False,
)
async def warehouse_delete(
    warehouse_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Роут мягкого удаления склада фулфилмента (ФФ) с сохранением остатков и истории движений.

    Args:
        warehouse_id: int - ID склада для удаления из URL.
        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        RedirectResponse - Редирект на главную страницу ("/") со статусом 303 See Other.

    Raises:
        HTTPException (400) - Не передан корректный ID склада или склад уже удалён.
        HTTPException (404) - Склад не найден.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info("POST /warehouse/delete/%s", warehouse_id)

    await delete_warehouse(db=db, warehouse_id=warehouse_id)

    main_log.info("POST /warehouse/delete/%s -> 303 Redirect", warehouse_id)

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )
