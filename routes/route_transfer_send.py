import logging.config
from typing import Annotated

from core import dict_config
from database import get_db
from fastapi import APIRouter, Depends, Form, status
from fastapi.responses import RedirectResponse
from schemas import TransferIn
from sqlalchemy.ext.asyncio import AsyncSession
from src import send_transfer

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("route_logger")
main_log.setLevel(logging.DEBUG)

router = APIRouter()


@router.post(
    "/movement/transfer/send/",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        303: {"description": "Редирект после отправки перемещения"},
        400: {"description": "Нехватка товара или некорректные склады"},
        404: {"description": "Товар или склад не найден"},
        500: {"description": "Ошибка БД"},
    },
    include_in_schema=False,
)
async def transfer_send(
    transfer_data: Annotated[TransferIn, Form()],
    db: AsyncSession = Depends(get_db),
):
    """
    Роут оформления отправки перемещения товара между складами фулфилмента (ФФ) через HTML-форму.

    Args:
        transfer_data: TransferIn - Pydantic модель из данных формы, включающая в себя:
            product_id - ID товара (артикула).
            from_warehouse_id - ID склада-отправителя (ФФ).
            to_warehouse_id - ID склада-получателя (ФФ).
            qty - Количество единиц товара для перемещения.



        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        RedirectResponse - Редирект на главную страницу ("/") со статусом 303 See Other.

    Raises:
        HTTPException (400) - Нехватка доступного товара на складе-отправителе, совпадение складов или склад удалён.
        HTTPException (404) - Товар или один из складов не найден.
        HTTPException (422) - Ошибка валидации полей формы (некорректные ID или количество).
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info(
        "POST /movement/transfer/send/ | product_id=%s, from_warehouse_id=%s, to_warehouse_id=%s, qty=%s",
        transfer_data.product_id,
        transfer_data.from_warehouse_id,
        transfer_data.to_warehouse_id,
        transfer_data.qty,
    )

    await send_transfer(
        db=db,
        product_id=transfer_data.product_id,
        from_warehouse_id=transfer_data.from_warehouse_id,
        to_warehouse_id=transfer_data.to_warehouse_id,
        qty=transfer_data.qty,
    )

    main_log.info(
        "POST /movement/transfer/send/ -> 303 Redirect (product_id=%s, from_warehouse_id=%s, to_warehouse_id=%s, qty=%s)",
        transfer_data.product_id,
        transfer_data.from_warehouse_id,
        transfer_data.to_warehouse_id,
        transfer_data.qty,
    )

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )
