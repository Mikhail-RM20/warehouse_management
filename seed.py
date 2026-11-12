import asyncio

from database import (
    Base,
    Movement,
    Products,
    SessionLocal,
    StockItem,
    Warehouse,
    engine,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_initial_data(db: AsyncSession) -> None:
    """
    Заполняет базу данных тестовыми складами, товарами и начальным приходом из ТЗ,
    если таблица товаров пуста.

    Args:
        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        None
    """
    # Проверяем, есть ли уже хотя бы один товар в БД (защита от повторного заполнения при перезапуске)
    existing_products = await db.execute(select(Products).limit(1))
    if existing_products.scalar_one_or_none():
        return

    # Создаём два тестовых склада фулфилмента (ФФ) из ТЗ
    wh_north = Warehouse(name="Север")
    wh_south = Warehouse(name="Юг")
    db.add_all([wh_north, wh_south])
    # Делаем flush(), чтобы БД присвоила складам ID до коммита, но не завершаем транзакцию
    await db.flush()

    # Создаём три тестовых товара (артикула) из ТЗ
    p1 = Products(article="SKU-101", product="Органайзер")
    p2 = Products(article="SKU-102", product="Контейнер")
    p3 = Products(article="SKU-103", product="Корзина")
    db.add_all([p1, p2, p3])
    # Получаем сгенерированные ID для товаров
    await db.flush()

    # Таблица начальных остатков из ТЗ: (ID товара, ID склада, количество)
    initial_stock = [
        (p1.id, wh_north.id, 10),  # SKU-101 Органайзер: Север — 10 шт.
        (p1.id, wh_south.id, 6),  # SKU-101 Органайзер: Юг — 6 шт.
        (p2.id, wh_north.id, 5),  # SKU-102 Контейнер: Север — 5 шт.
        (p2.id, wh_south.id, 0),  # SKU-102 Контейнер: Юг — 0 шт.
        (p3.id, wh_north.id, 0),  # SKU-103 Корзина: Север — 0 шт.
        (p3.id, wh_south.id, 4),  # SKU-103 Корзина: Юг — 4 шт.
    ]

    for product_id, warehouse_id, qty in initial_stock:
        # Создаём запись об остатке товара на конкретном складе
        db.add(
            StockItem(
                product_id=product_id,
                warehouse_id=warehouse_id,
                qty_on_hand=qty,
                qty_reserved_fbs=0,
            )
        )
        # Если начальный остаток больше нуля — фиксируем операцию прихода (INBOUND) в истории движений
        if qty > 0:
            db.add(
                Movement(
                    product_id=product_id,
                    qty=qty,
                    movement_type="INBOUND",
                    from_warehouse_id=None,
                    to_warehouse_id=warehouse_id,
                    status="COMPLETED",
                )
            )

    # Сохраняем все созданные склады, товары, остатки и историю приходов одной транзакцией
    await db.commit()


async def main() -> None:
    """
    Точка входа для ручного запуска скрипта заполнения БД из терминала (python seed.py).
    """
    # Создаём все таблицы в PostgreSQL по моделям SQLAlchemy, если они ещё не созданы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Открываем сессию и запускаем загрузку тестовых данных
    async with SessionLocal() as db:
        await seed_initial_data(db)
        print("Тестовые данные успешно загружены.")


if __name__ == "__main__":
    # Запускаем асинхронную функцию main() при прямом вызове файла
    asyncio.run(main())
