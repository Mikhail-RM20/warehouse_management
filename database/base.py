from collections.abc import AsyncGenerator

from core import config_set
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

# Создаем асинхронный движок для подключения к PostgreSQL.
engine = create_async_engine(config_set.database_url, echo=True)

# Создаем класс для моделей ORM.
Base = declarative_base()

# Создаем фабрику сессий.
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


# Создаем асинхронную функцию, которая содержит контекстный менеджер.
# Позволяет по запросу автоматически открывать сессию и закрывать ее.
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
