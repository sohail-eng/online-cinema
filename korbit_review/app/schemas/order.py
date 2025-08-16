from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, computed_field, ConfigDict

from app.models.order import OrderStatusEnum
from app.schemas.movie import MovieCartRead, MovieOrderItemView
from app.schemas.user import UserProfileRead


class OrderItemBaseSchema(BaseModel):
    id: int
    order_id: int
    price_at_order: Decimal

    model_config = ConfigDict(
        from_attributes=True
    )

class OrderItemReadSchema(OrderItemBaseSchema):
    movie: MovieCartRead


class OrderItemDetailSchema(OrderItemBaseSchema):
    movie: MovieOrderItemView


class OrderBaseSchema(BaseModel):
    id: int
    created_at: datetime
    status: OrderStatusEnum
    total_amount: Decimal

    model_config = ConfigDict(
        from_attributes=True
    )

class OrderListSchema(OrderBaseSchema):
    user_profile_id: UserProfileRead
    order_items: List[OrderItemReadSchema]

    @computed_field(return_type=int)
    def order_items_count(self):
        return len(self.order_items)

class OrdersPaginatedSchema(BaseModel):
    limit: Optional[int] = None
    offset: Optional[int] = None
    total_items: Optional[int] = None

    items: List[OrderListSchema]


class OrderDetailSchema(OrderBaseSchema):
    user_profile: UserProfileRead
    order_items: List[OrderItemDetailSchema]

    @computed_field(return_type=int)
    def order_items_count(self):
        return len(self.order_items)


class OrderDetailPaginatedSchema(BaseModel):
    offset: Optional[int] = None
    limit: Optional[int] = None
    total_items: Optional[int] = None

    orders: OrderDetailSchema