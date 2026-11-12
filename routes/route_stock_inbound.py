import logging.config
from typing import Annotated

from core import dict_config
from database import get_db
from fastapi import APIRouter, Depends, Form, status
from fastapi.responses import RedirectResponse
from schemas import InboundIn
from sqlalchemy.ext.asyncio import AsyncSession
from src import add_inbound

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("route_logger")
main_log.setLevel(logging.DEBUG)


router = APIRouter()


@router.post(
    "/stock/inbound/",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        303: {"description": "Редирект после оформления прихода"},
        400: {"description": "Некорректные параметры или склад удален"},
        404: {"description": "Товар или склад не найден"},
        500: {"description": "Ошибка БД"},
    },
    include_in_schema=False,
)
async def stock_inbound(
    inbound_data: Annotated[InboundIn, Form()],
    db: AsyncSession = Depends(get_db),
):
    """
    Роут оформления прихода товара на выбранный склад фулфилмента (ФФ) через HTML-форму.

    Args:
        inbound_data: InboundIn - Pydantic модель из данных формы, включающая в себя:
            product_id - ID товара (артикула).
            warehouse_id - ID склада-получателя (ФФ).
            qty - Количество единиц товара, поступающих на склад.


        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        RedirectResponse - Редирект на главную страницу ("/") со статусом 303 See Other.

    Raises:
        HTTPException (400) - Некорректные параметры или попытка оформить приход на удалённый склад.
        HTTPException (404) - Товар или склад не найден.
        HTTPException (422) - Ошибка валидации полей формы (некорректные ID или количество).
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "POST /stock/inbound/ | product_id=%s, warehouse_id=%s, qty=%s",
        inbound_data.product_id,
        inbound_data.warehouse_id,
        inbound_data.qty,
    )

    await add_inbound(
        db=db,
        product_id=inbound_data.product_id,
        warehouse_id=inbound_data.warehouse_id,
        qty=inbound_data.qty,
    )

    main_log.info(
        "POST /stock/inbound/ -> 303 Redirect (product_id=%s, warehouse_id=%s, qty=%s)",
        inbound_data.product_id,
        inbound_data.warehouse_id,
        inbound_data.qty,
    )

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )
