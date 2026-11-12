import logging.config
from typing import Annotated

from core import dict_config
from database import get_db
from fastapi import APIRouter, Depends, Form, status
from fastapi.responses import RedirectResponse
from schemas import WarehouseIn
from sqlalchemy.ext.asyncio import AsyncSession
from src import add_warehouse

router = APIRouter()


logging.config.dictConfig(dict_config)
main_log = logging.getLogger("route_logger")
main_log.setLevel(logging.DEBUG)


@router.post(
    "/warehouse/add/",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        303: {"description": "Редирект после создания"},
        409: {"description": "Склад с таким названием уже существует"},
        500: {"description": "Ошибка БД"},
    },
    include_in_schema=False,
)
async def warehouse_add(
    warehouse_data: Annotated[WarehouseIn, Form()],
    db: AsyncSession = Depends(get_db),
):
    """
    Роут создания нового склада фулфилмента (ФФ) через HTML-форму.

    Args:
        warehouse_data: WarehouseIn - Pydantic модель из данных формы, включающая в себя:
            name - Название нового склада.


        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        RedirectResponse - Редирект на главную страницу ("/") со статусом 303 See Other.

    Raises:
        HTTPException (409) - Склад с таким названием уже существует.
        HTTPException (422) - Ошибка валидации полей формы (пустое название).
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info("POST /warehouse/add/ | name=%s", warehouse_data.name)

    await add_warehouse(db=db, name_warehouse=warehouse_data.name)

    main_log.info(
        "POST /warehouse/add/ -> 303 Redirect (name=%s)", warehouse_data.name
    )

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )
