"""
Точка входа веб-приложения CheckStock.

Инициализирует FastAPI, создаёт таблицы в БД и загружает тестовые данные при старте,
настраивает обработку ошибок для HTML-форм и подключает все маршруты приложения.
"""

from contextlib import asynccontextmanager
from urllib.parse import quote

from database import Base, SessionLocal, engine
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from routes import (
    add_warehouse,
    cancel_fbs,
    fbo_rec,
    fbs_rec,
    fbs_ship,
    index,
    rename_warehouse,
    send_fbo,
    soft_delete_warehouse,
    stock_inbound,
    transfer_receive,
    transfer_send,
)
from seed import seed_initial_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управляет жизненным циклом приложения: при старте создаёт таблицы в PostgreSQL
    и заполняет их тестовыми данными из ТЗ (если база пуста).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        await seed_initial_data(db)

    yield


app = FastAPI(
    title="CheckStock — Учёт остатков и движений",
    lifespan=lifespan,
)


app.mount(
    "/images",
    StaticFiles(directory="images"),
    name="images",
)


@app.exception_handler(HTTPException)
async def http_exception_redirect_handler(
    request: Request, exc: HTTPException
):
    """
    Перехватывает бизнес-исключения (нехватка товара на складе, дубликат названия,
    повторное подтверждение операции) и перенаправляет пользователя на главный экран
    с текстом ошибки для отображения в уведомлении.
    """
    return RedirectResponse(
        url=f"/?error={quote(str(exc.detail))}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# Подключение главного экрана остатков (GET /)
app.include_router(index)

# Подключение роутов управления складами ФФ
app.include_router(add_warehouse)
app.include_router(rename_warehouse)
app.include_router(soft_delete_warehouse)

# Подключение роутов прихода и перемещений между ФФ
app.include_router(stock_inbound)
app.include_router(transfer_send)
app.include_router(transfer_receive)

# Подключение роутов отправок FBS и FBO
app.include_router(fbs_rec)
app.include_router(fbs_ship)
app.include_router(cancel_fbs)
app.include_router(send_fbo)
app.include_router(fbo_rec)
