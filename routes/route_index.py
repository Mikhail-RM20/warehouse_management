from database import Movement, Products, StockItem, Warehouse, get_db
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Создаём экземпляр роутера для главного экрана
router = APIRouter()
# Указываем папку templates/, в которой лежит HTML-шаблон index.html
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(
    request: Request,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Роут отображения главного экрана остатков CheckStock (Пункт 01 ТЗ).

    Собирает остатки по всем складам ФФ (включая удалённые склады, на которых
    числится товар), активные резервы FBS, товары в пути (между ФФ, по FBO и FBS),
    список складов и полную историю операций для рендеринга в HTML-шаблоне.

    Args:
        request: Request - Объект входящего HTTP-запроса FastAPI (обязателен для Jinja2).
        error: str | None - Текст ошибки из query-параметра URL после редиректа (если возникла).
        db: AsyncSession - Асинхронная сессия БД.

    Returns:
        HTMLResponse - Отрендеренный HTML-шаблон templates/index.html.
    """
    # 1. Загружаем все склады из БД (и активные, и удалённые), отсортированные по ID
    wh_res = await db.execute(select(Warehouse).order_by(Warehouse.id))
    warehouses = wh_res.scalars().all()
    # Делаем словарь {id_склада: объект_склада} для быстрого поиска названия без лишних запросов к БД
    wh_map = {w.id: w for w in warehouses}
    # Отбираем только активные склады (is_deleted == False) для выпадающих списков в формах
    active_warehouses = [w for w in warehouses if not w.is_deleted]

    # 2. Загружаем все товары (артикулы) и формируем словарь {id_товара: объект_товара}
    prod_res = await db.execute(select(Products).order_by(Products.id))
    products = prod_res.scalars().all()
    prod_map = {p.id: p for p in products}

    # 3. Загружаем все записи остатков по связке (товар + склад)
    stock_res = await db.execute(
        select(StockItem).order_by(
            StockItem.product_id, StockItem.warehouse_id
        )
    )
    stock_items_raw = stock_res.scalars().all()

    # Формируем список строк для первой таблицы «Остатки по складам ФФ»
    stocks = []
    for item in stock_items_raw:
        wh = wh_map.get(item.warehouse_id)
        prod = prod_map.get(item.product_id)
        if not wh or not prod:
            continue
        # Если склад удалён, не показываем пустые нулевые строки; оставляем только те, где ещё числится товар
        if (
            wh.is_deleted
            and item.qty_on_hand == 0
            and item.qty_reserved_fbs == 0
        ):
            continue
        stocks.append(
            {
                "article": prod.article,
                "product": prod.product,
                "warehouse_name": wh.name,
                "warehouse_deleted": wh.is_deleted,
                "qty_on_hand": item.qty_on_hand,  # Физически на складе
                "qty_reserved_fbs": item.qty_reserved_fbs,  # Заблокировано в резерве FBS
                "qty_available": item.qty_on_hand
                - item.qty_reserved_fbs,  # Доступно к отгрузке
            }
        )

    # 4. Загружаем всю историю движений (новые операции сверху)
    mov_res = await db.execute(select(Movement).order_by(Movement.id.desc()))
    movements_raw = mov_res.scalars().all()

    active_movements = []  # Список только активных резервов и товаров в пути (для блока действий)
    history = []  # Полный лог всех операций (для нижней таблицы истории)

    # Словарь перевода технических статусов в понятные подписи для менеджера
    status_labels = {
        "RESERVED": "В резерве FBS",
        "IN_TRANSIT": "В пути",
        "COMPLETED": "Завершено",
        "CANCELLED": "Отменено",
    }

    for m in movements_raw:
        prod = prod_map.get(m.product_id)
        from_wh = (
            wh_map.get(m.from_warehouse_id) if m.from_warehouse_id else None
        )
        to_wh = wh_map.get(m.to_warehouse_id) if m.to_warehouse_id else None

        # Формируем названия складов с пометкой «(удалён)», если склад был удалён
        from_name = (
            f"{from_wh.name}{' (удалён)' if from_wh.is_deleted else ''}"
            if from_wh
            else "—"
        )
        to_name = (
            f"{to_wh.name}{' (удалён)' if to_wh.is_deleted else ''}"
            if to_wh
            else "—"
        )

        # Определяем человекочитаемый тип операции и направление «Откуда -> Куда»
        if m.movement_type == "INBOUND":
            type_label = "Приход на ФФ"
            from_label = "Поставщик"
            to_label = to_name
        elif m.movement_type == "TRANSFER":
            type_label = "Перемещение между ФФ"
            from_label = from_name
            to_label = to_name
        elif m.movement_type == "FBS":
            type_label = "Заказ FBS"
            from_label = from_name
            to_label = "Клиент (FBS)"
        elif m.movement_type == "FBO":
            type_label = "Поставка FBO"
            from_label = from_name
            to_label = "Склад маркетплейса (FBO)"
        else:
            type_label = m.movement_type
            from_label = from_name
            to_label = to_name

        row = {
            "id": m.id,
            "created_at": m.created_at.strftime("%d.%m.%Y %H:%M")
            if m.created_at
            else "",
            "article": prod.article if prod else "—",
            "product": prod.product if prod else "—",
            "qty": m.qty,
            "movement_type": m.movement_type,
            "type_label": type_label,
            "from_label": from_label,
            "to_label": to_label,
            "status": m.status,
            "status_label": status_labels.get(m.status, m.status),
        }
        # Добавляем каждую операцию в общую историю
        history.append(row)

        # Если операция ещё не завершена (в резерве FBS или в пути) — дублируем в таблицу активных движений
        if m.status in ("RESERVED", "IN_TRANSIT"):
            active_movements.append(row)

    # 5. Передаём все собранные списки и возможную ошибку в HTML-шаблон и возвращаем страницу
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "error": error,
            "warehouses": warehouses,
            "active_warehouses": active_warehouses,
            "products": products,
            "stocks": stocks,
            "active_movements": active_movements,
            "history": history,
        },
    )
