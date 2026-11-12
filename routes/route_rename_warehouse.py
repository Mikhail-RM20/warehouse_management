import logging.config
from typing import Annotated

from core import dict_config
from database import get_db
from fastapi import APIRouter, Depends, Form, status
from fastapi.responses import RedirectResponse
from schemas import WarehouseIn
from sqlalchemy.ext.asyncio import AsyncSession
from src import rename_warehouse

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("route_logger")
main_log.setLevel(logging.DEBUG)

router = APIRouter()


@router.post(
    "/warehouse/rename/{warehouse_id}",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        303: {"description": "Редирект после создания"},
        400: {
            "description": "Не передан параметр (Название склада / ID-склада)"
        },
        404: {"description": "Склад не найден"},
        500: {"description": "Ошибка БД"},
    },
    include_in_schema=False,
)
async def warehouse_rename(
    warehouse_id: int,
    warehouse_data: Annotated[WarehouseIn, Form()],
    db: AsyncSession = Depends(get_db),
):
    """
    Роут переименования существующего склада фулфилмента (ФФ) через HTML-форму.

    Args:
        warehouse_id: int - ID склада для переименования из URL.
        warehouse_data: WarehouseIn - Pydantic модель из данных формы, включающая в себя:
            name - Новое название склада.


        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        RedirectResponse - Редирект на главную страницу ("/") со статусом 303 See Other.

    Raises:
        HTTPException (400) - Не передан корректный ID склада, пустое название или склад удалён.
        HTTPException (404) - Склад не найден.
        HTTPException (422) - Ошибка валидации полей формы.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "POST /warehouse/rename/%s | name=%s",
        warehouse_id,
        warehouse_data.name,
    )

    await rename_warehouse(
        db=db, warehouse_id=warehouse_id, warehouse_name=warehouse_data.name
    )

    main_log.info(
        "POST /warehouse/rename/%s -> 303 Redirect (name=%s)",
        warehouse_id,
        warehouse_data.name,
    )

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )
