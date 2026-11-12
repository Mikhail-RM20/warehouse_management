from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Products(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    article: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    product: Mapped[str] = mapped_column(String, nullable=False)


class Warehouse(Base):
    __tablename__ = "warehouse"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


class StockItem(Base):
    __tablename__ = "stock_item"
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"))
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouse.id")
    )
    qty_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    qty_reserved_fbs: Mapped[int] = mapped_column(default=0)


class Movement(Base):
    __tablename__ = "movement"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[int]
    movement_type: Mapped[str] = mapped_column(String(50))
    from_warehouse_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("warehouse.id"),
        nullable=True,
    )
    to_warehouse_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("warehouse.id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
