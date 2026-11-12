import logging.config

from core import dict_config
from database import get_db
from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src import receive_transfer

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("route_logger")
main_log.setLevel(logging.DEBUG)

router = APIRouter()


@router.post(
    "/movement/transfer/receive/{movement_id}",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        303: {"description": "Редирект после приёмки перемещения"},
        400: {"description": "Перемещение уже принято или некорректный ID"},
        404: {"description": "Перемещение не найдено"},
        500: {"description": "Ошибка БД"},
    },
    include_in_schema=False,
)
async def transfer_receive(
    movement_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Роут подтверждения приёмки перемещения товара на складе-получателе (ФФ).

    Args:
        movement_id: int - ID записи движения (перемещения между ФФ) из URL.
        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        RedirectResponse - Редирект на главную страницу ("/") со статусом 303 See Other.

    Raises:
        HTTPException (400) - Некорректный ID перемещения или перемещение уже принято/отменено.
        HTTPException (404) - Перемещение не найдено.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info("POST /movement/transfer/receive/%s", movement_id)

    await receive_transfer(db=db, movement_id=movement_id)

    main_log.info(
        "POST /movement/transfer/receive/%s -> 303 Redirect", movement_id
    )

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )
