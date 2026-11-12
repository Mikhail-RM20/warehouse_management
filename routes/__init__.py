from .route_add_warehouse import router as add_warehouse
from .route_cancel_fbs import router as cancel_fbs
from .route_fbo_recive import router as fbo_rec
from .route_fbs_recive import router as fbs_rec
from .route_fbs_ship import router as fbs_ship
from .route_index import router as index
from .route_rename_warehouse import router as rename_warehouse
from .route_send_fbo import router as send_fbo
from .route_softdelete_warehouse import router as soft_delete_warehouse
from .route_stock_inbound import router as stock_inbound
from .route_transfer_receive import router as transfer_receive
from .route_transfer_send import router as transfer_send

__all__ = [
    "add_warehouse",
    "cancel_fbs",
    "fbo_rec",
    "fbs_rec",
    "fbs_ship",
    "rename_warehouse",
    "send_fbo",
    "soft_delete_warehouse",
    "stock_inbound",
    "transfer_receive",
    "transfer_send",
    "index",
]
