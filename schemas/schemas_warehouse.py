from pydantic import BaseModel, Field


class WarehouseIn(BaseModel):
    name: str = Field(..., min_length=1, title="Название склада")
