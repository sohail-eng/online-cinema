from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentStatusEnum
from app.schemas.order import OrderDetailSchema
from app.schemas.user import UserProfileRead


class UserPaymentList(BaseModel):
    id: int
    user_profile_id: int
    order_id: int
    status: PaymentStatusEnum
    amount: Decimal
    external_payment_id: str
    count_of_items: Optional[int]

    model_config = ConfigDict(
        from_attributes=True
    )


class AdminPaymentList(UserPaymentList):
    user_profile: UserProfileRead


class AdminPaginatedList(BaseModel):
    payments: List[AdminPaymentList]
    total_items: Optional[int] = 0


class PaginatedUserPaymentList(BaseModel):
    payments: List[UserPaymentList]
    total_items: Optional[int] = 0


class PaginatedAdminPaymentList(BaseModel):
    payments: List[UserPaymentList]
    total_items: Optional[int] = 0


class PaymentItemSchema(BaseModel):
    id: int
    payment_id: int
    order_item_id: int
    price_at_payment: Decimal

    model_config = ConfigDict(
        from_attributes=True
    )


class UserPaymentDetailSchema(UserPaymentList):
    order: OrderDetailSchema
    payment_items: List[PaymentItemSchema]


class AdminPaymentDetailSchema(UserPaymentDetailSchema):
    pass