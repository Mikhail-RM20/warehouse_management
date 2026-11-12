from pydantic import BaseModel, Field


class InboundIn(BaseModel):
    product_id: int = Field(..., gt=0, title="Товар")
    warehouse_id: int = Field(..., gt=0, title="Склад")
    qty: int = Field(..., gt=0, title="Количество")
