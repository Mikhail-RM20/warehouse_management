import logging.config
from typing import Annotated

from core import dict_config
from database import get_db
from fastapi import APIRouter, Depends, Form, status
from fastapi.responses import RedirectResponse
from schemas import ShipmentIn
from sqlalchemy.ext.asyncio import AsyncSession
from src import reserve_fbs

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("route_logger")
main_log.setLevel(logging.DEBUG)

router = APIRouter()


@router.post(
    "/movement/fbs/reserve/",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        303: {"description": "Редирект после создания резерва FBS"},
        400: {
            "description": "Нехватка товара на складе или некорректные параметры"
        },
        404: {"description": "Товар или склад не найден"},
        500: {"description": "Ошибка БД"},
    },
    include_in_schema=False,
)
async def fbs_reserve(
    shipment_data: Annotated[ShipmentIn, Form()],
    db: AsyncSession = Depends(get_db),
):
    """
    Роут создания резерва FBS на выбранном складе через HTML-форму.

    Args:
        shipment_data: ShipmentIn - Pydantic модель из данных формы, включающая в себя:
            product_id - ID товара (артикула).
            warehouse_id - ID склада-отправителя (ФФ).
            qty - Количество единиц товара для резервирования.


        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        RedirectResponse - Редирект на главную страницу ("/") со статусом 303 See Other.

    Raises:
        HTTPException (400) - Нехватка доступного товара на складе или склад удалён.
        HTTPException (404) - Товар или склад не найден.
        HTTPException (422) - Ошибка валидации полей формы (некорректные ID или количество).
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "POST /movement/fbs/reserve/ | product_id=%s, warehouse_id=%s, qty=%s",
        shipment_data.product_id,
        shipment_data.warehouse_id,
        shipment_data.qty,
    )

    await reserve_fbs(
        db=db,
        product_id=shipment_data.product_id,
        warehouse_id=shipment_data.warehouse_id,
        qty=shipment_data.qty,
    )

    main_log.info(
        "POST /movement/fbs/reserve/ -> 303 Redirect (product_id=%s, warehouse_id=%s, qty=%s)",
        shipment_data.product_id,
        shipment_data.warehouse_id,
        shipment_data.qty,
    )

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )
