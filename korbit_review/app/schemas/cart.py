from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from app.schemas.movie import MovieCartRead
from app.schemas.user import UserProfileRead


class CartItemsReadSchema(BaseModel):
     id: int
     cart_id: int
     movie_id: int
     added_at: int
     is_paid: bool

     movie: MovieCartRead

     model_config = ConfigDict(
         from_attributes=True
     )


class CartPurchasedReadSchema(BaseModel):
    cart_id: int
    user_profile: UserProfileRead
    cart_items: Optional[List[CartItemsReadSchema]] = []

    #cutom
    count_of_all_items_in_cart: Optional[int] = 0

    model_config = ConfigDict(
        from_attributes=True
    )


class CartReadSchema(CartPurchasedReadSchema):
    #cutom
    total_price: Optional[Decimal] = None


class AdminCartsSchema(BaseModel):
    cart_id: int
    user_profile: UserProfileRead

    #cutom
    count_of_all_items_in_cart: Optional[int] = 0


class AdminCartsPaginatedSchema(BaseModel):
    total_items: Optional[int] = 0
    carts: List[AdminCartsSchema] = []
