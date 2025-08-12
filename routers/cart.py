from typing import List

from fastapi import APIRouter, HTTPException
from starlette import status
from starlette.responses import JSONResponse

import crud
import dependencies
import models
import schemas
from exceptions import SomethingWentWrongError, MovieAlreadyIsPurchasedOrInCartError
from models import Cart

router = APIRouter()


@router.post("/cart/add_item/{movie_id}/")
async def cart_add_item_endpoint(
        movie_id: int,
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
) -> JSONResponse:
    try:
        added_item = await crud.cart_add_item(db=db, user_profile=user.user_profile, movie_id=movie_id)
    except MovieAlreadyIsPurchasedOrInCartError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Movie is already purchased or in cart.")

    if not isinstance(added_item, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{added_item.get('detail')}", status_code=status.HTTP_200_OK)


@router.delete("/cart/remove_item/{movie_id}")
async def cart_remove_item_endpoint(
        movie_id: int,
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser
) -> JSONResponse:

    removed_item = await crud.cart_remove_item(
        db=db,
        movie_id=movie_id,
        user_profile=user.user_profile
    )

    if not isinstance(removed_item, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{removed_item.get('detail')}", status_code=status.HTTP_200_OK)


@router.get("/cart/items/", response_model=schemas.CartReadSchema)
async def cart_list_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        search_by_book_name: str = None
) -> schemas.CartReadSchema:
    cart_items = await crud.cart_items_list(
        db=db,
        user_profile=user.user_profile,
        search_by_book_name=search_by_book_name
    )
    if not cart_items:
        raise SomethingWentWrongError

    if not isinstance(cart_items, dict):
        raise SomethingWentWrongError

    cart_items_list = [schemas.CartItemsReadSchema.model_validate(item) for item in cart_items.get("cart_items", [])]

    return schemas.CartReadSchema(
        cart_id=cart_items.get("id", None),
        cart_items=cart_items_list,
        user_profile=user.user_profile,
        total_price=cart_items.get("total_price"),
    )



@router.get("/cart/purchased_items/", response_model=schemas.CartPurchasedReadSchema)
async def cart_purchased_items_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        search_by_book_name: str = None
) -> schemas.CartPurchasedReadSchema:

    purchased_cart = await crud.cart_purchased_items(
        db=db,
        user_profile=user.user_profile,
        search_by_book_name=search_by_book_name
    )

    if not isinstance(purchased_cart, dict):
        raise SomethingWentWrongError

    validated_items = [schemas.CartItemsReadSchema.model_validate(item) for item in purchased_cart.get("cart_items")]

    return schemas.CartPurchasedReadSchema(
        cart_id=purchased_cart.get("cart_id", None),
        cart_items=validated_items,
        user_profile=user.user_profile
    )
