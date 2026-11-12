from pydantic import BaseModel, Field


class ShipmentIn(BaseModel):
    product_id: int = Field(..., gt=0, title="Товар")
    warehouse_id: int = Field(..., gt=0, title="Склад-отправитель")
    qty: int = Field(..., gt=0, title="Количество")
