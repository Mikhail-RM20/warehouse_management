import logging.config

from core import dict_config
from database import get_db
from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src import receive_fbo

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("route_logger")
main_log.setLevel(logging.DEBUG)


router = APIRouter()


@router.post(
    "/movement/fbo/receive/{movement_id}",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        303: {"description": "Редирект после приёмки поставки FBO"},
        400: {"description": "Поставка FBO уже принята или отменена"},
        404: {"description": "Поставка FBO не найдена"},
        500: {"description": "Ошибка БД"},
    },
    include_in_schema=False,
)
async def fbo_receive(
    movement_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Роут подтверждения приёмки поставки FBO на складе маркетплейса.

    Args:
        movement_id: int - ID записи движения (поставки FBO) из URL.
        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        RedirectResponse - Редирект на главную страницу ("/") со статусом 303 See Other.

    Raises:
        HTTPException (400) - Некорректный ID поставки или поставка FBO уже принята/отменена.
        HTTPException (404) - Поставка FBO не найдена.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info("POST /movement/fbo/receive/%s", movement_id)

    await receive_fbo(db=db, movement_id=movement_id)

    main_log.info("POST /movement/fbo/receive/%s -> 303 Redirect", movement_id)

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )
