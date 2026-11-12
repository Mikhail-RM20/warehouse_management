import logging.config

from core import dict_config
from database import get_db
from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src import cancel_fbs

logging.config.dictConfig(dict_config)
main_log = logging.getLogger("route_logger")
main_log.setLevel(logging.DEBUG)
router = APIRouter()


@router.post(
    "/movement/fbs/cancel/{movement_id}",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        303: {"description": "Редирект после отмены резерва FBS"},
        400: {"description": "Можно отменить только активный резерв FBS"},
        404: {"description": "Заказ FBS не найден"},
        500: {"description": "Ошибка БД"},
    },
    include_in_schema=False,
)
async def fbs_cancel(
    movement_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Роут отмены активного резерва FBS и возврата товара в доступный остаток склада.

    Args:
        movement_id: int - ID записи движения (резерва FBS) из URL.
        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        RedirectResponse - Редирект на главную страницу ("/") со статусом 303 See Other.

    Raises:
        HTTPException (400) - Некорректный ID заказа или резерв уже отправлен/отменён.
        HTTPException (404) - Заказ FBS не найден.
        HTTPException (500) - Внутренняя ошибка БД.
    """
    main_log.info("POST /movement/fbs/cancel/%s", movement_id)

    await cancel_fbs(db=db, movement_id=movement_id)

    main_log.info("POST /movement/fbs/cancel/%s -> 303 Redirect", movement_id)

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )
