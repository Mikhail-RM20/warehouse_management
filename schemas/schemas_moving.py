from pydantic import BaseModel, Field


class TransferIn(BaseModel):
    product_id: int = Field(..., gt=0, title="Товар")
    from_warehouse_id: int = Field(..., gt=0, title="Склад-отправитель")
    to_warehouse_id: int = Field(..., gt=0, title="Склад-получатель")
    qty: int = Field(..., gt=0, title="Количество")
