from dataclasses import dataclass, asdict
from typing import Optional, Literal, TypedDict, List, Any

StockStatus = Literal["IN STOCK", "LOW STOCK", "OUT OF STOCK", "NOT PRESCRIBABLE"]


@dataclass
class Item:
    product_id: Optional[str]
    producer: Optional[str]
    brand: Optional[str]
    strain: Optional[str]
    strain_type: Optional[str]
    stock: Optional[str]
    product_type: Optional[str]
    stock_status: Optional[str] = None
    stock_detail: Optional[str] = None
    stock_remaining: Optional[int] = None
    is_smalls: bool = False
    grams: Optional[float] = None
    ml: Optional[float] = None
    price: Optional[float] = None
    thc: Optional[float] = None
    thc_unit: Optional[str] = None
    cbd: Optional[float] = None
    cbd_unit: Optional[str] = None
    requestable: Optional[bool] = None
    is_active: Optional[bool] = None
    is_inactive: Optional[bool] = None
    status: Optional[str] = None
    price_delta: Optional[float] = None
    is_new: bool = False
    is_removed: bool = False


class ItemDict(TypedDict, total=False):
    product_id: Optional[str]
    producer: Optional[str]
    brand: Optional[str]
    strain: Optional[str]
    strain_type: Optional[str]
    stock: Optional[str]
    stock_status: Optional[str]
    stock_detail: Optional[str]
    stock_remaining: Optional[int]
    product_type: Optional[str]
    is_smalls: bool
    grams: Optional[float]
    ml: Optional[float]
    price: Optional[float]
    thc: Optional[float]
    thc_unit: Optional[str]
    cbd: Optional[float]
    cbd_unit: Optional[str]
    requestable: Optional[bool]
    is_active: Optional[bool]
    is_inactive: Optional[bool]
    status: Optional[str]
    price_delta: Optional[float]
    is_new: bool
    is_removed: bool


class ChangeLogRecord(TypedDict, total=False):
    timestamp: str
    new_count: int
    removed_count: int
    price_changes: List[str]
    stock_changes: List[str]
    new_items: List[str]
    removed_items: List[str]


class HaPayload(TypedDict, total=False):
    new_count: int
    removed_count: int
    price_changes: list
    stock_changes: list
    new_item_summaries: list
    removed_item_summaries: list
    price_change_summaries: list
    stock_change_summaries: list
    new_flowers: list
    removed_flowers: list


def item_from_dict(data: dict) -> Item:
    """Create a typed Item from a loose dict."""
    return Item(
        product_id=data.get("product_id"),
        producer=data.get("producer"),
        brand=data.get("brand"),
        strain=data.get("strain"),
        strain_type=data.get("strain_type"),
        stock=data.get("stock"),
        stock_status=data.get("stock_status"),
        stock_detail=data.get("stock_detail"),
        stock_remaining=data.get("stock_remaining"),
        product_type=data.get("product_type"),
        is_smalls=bool(data.get("is_smalls", False)),
        grams=data.get("grams"),
        ml=data.get("ml"),
        price=data.get("price"),
        thc=data.get("thc"),
        thc_unit=data.get("thc_unit"),
        cbd=data.get("cbd"),
        cbd_unit=data.get("cbd_unit"),
        requestable=data.get("requestable"),
        is_active=data.get("is_active"),
        is_inactive=data.get("is_inactive"),
        status=data.get("status"),
        price_delta=data.get("price_delta"),
        is_new=bool(data.get("is_new", False)),
        is_removed=bool(data.get("is_removed", False)),
    )


def item_to_dict(item: Item) -> ItemDict:
    """Convert Item dataclass to a dict suitable for persistence/exports."""
    return ItemDict(**asdict(item))
