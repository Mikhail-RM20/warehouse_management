import logging.config

from core import dict_config
from database import get_db
from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src import ship_fbs

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("route_logger")
main_log.setLevel(logging.DEBUG)

router = APIRouter()


@router.post(
    "/movement/fbs/ship/{movement_id}",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        303: {"description": "Редирект после отправки заказа FBS клиенту"},
        400: {
            "description": "Заказ уже отправлен, отменён или ошибка остатков"
        },
        404: {"description": "Заказ FBS не найден"},
        500: {"description": "Ошибка БД"},
    },
    include_in_schema=False,
)
async def fbs_ship(
    movement_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Роут подтверждения отправки зарезервированного заказа FBS клиенту.

    Args:
        movement_id: int - ID записи движения (заказа FBS) из URL.
        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        RedirectResponse - Редирект на главную страницу ("/") со статусом 303 See Other.

    Raises:
        HTTPException (400) - Некорректный ID заказа, заказ уже отправлен/отменён или ошибка остатков.
        HTTPException (404) - Заказ FBS не найден.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info("POST /movement/fbs/ship/%s", movement_id)

    await ship_fbs(db=db, movement_id=movement_id)

    main_log.info("POST /movement/fbs/ship/%s -> 303 Redirect", movement_id)

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )
