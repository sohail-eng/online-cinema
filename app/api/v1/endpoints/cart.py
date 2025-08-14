from typing import List, Any, Coroutine

from fastapi import APIRouter, HTTPException
from starlette import status
from starlette.responses import JSONResponse

from app.crud.cart import cart_add_item, cart_remove_item, cart_items_list as cart_user_list, cart_purchased_items, \
    admin_carts_list, admin_user_cart_detail
from app.models.cart import Cart
from app.schemas.cart import CartReadSchema, CartItemsReadSchema, CartPurchasedReadSchema, AdminCartsSchema, \
    AdminCartsPaginatedSchema
from app.utils.dependencies import GetCurrentUser, DpGetDB
from app.utils.exceptions import MovieAlreadyIsPurchasedOrInCartError, SomethingWentWrongError

router = APIRouter()


@router.post("/cart/add_item/{movie_id}/")
async def cart_add_item_endpoint(
        movie_id: int,
        db: DpGetDB,
        user: GetCurrentUser,
) -> JSONResponse:
    try:
        added_item = await cart_add_item(db=db, user_profile=user.user_profile, movie_id=movie_id)
    except MovieAlreadyIsPurchasedOrInCartError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Movie is already purchased or in cart.")

    if not isinstance(added_item, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{added_item.get('detail')}", status_code=status.HTTP_200_OK)


@router.delete("/cart/remove_item/{movie_id}")
async def cart_remove_item_endpoint(
        movie_id: int,
        db: DpGetDB,
        user: GetCurrentUser
) -> JSONResponse:
    removed_item = await cart_remove_item(
        db=db,
        movie_id=movie_id,
        user_profile=user.user_profile
    )

    if not isinstance(removed_item, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{removed_item.get('detail')}", status_code=status.HTTP_200_OK)


@router.get("/cart/items/", response_model=CartReadSchema)
async def cart_list_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        search_by_book_name: str = None
) -> CartReadSchema:
    cart_items = await cart_user_list(
        db=db,
        user_profile=user.user_profile,
        search_by_book_name=search_by_book_name
    )
    if not cart_items:
        raise SomethingWentWrongError

    if not isinstance(cart_items, dict):
        raise SomethingWentWrongError

    cart_items_list = [
        CartItemsReadSchema.model_validate(item)
        for item in cart_items.get("cart_items", [])
    ]

    return CartReadSchema(
        cart_id=cart_items.get("id", None),
        cart_items=cart_items_list,
        user_profile=user.user_profile,
        total_price=cart_items.get("total_price"),
    )


@router.get("/cart/purchased_items/", response_model=CartPurchasedReadSchema)
async def cart_purchased_items_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        search_by_book_name: str = None
) -> CartPurchasedReadSchema:
    purchased_cart = await cart_purchased_items(
        db=db,
        user_profile=user.user_profile,
        search_by_book_name=search_by_book_name
    )

    if not isinstance(purchased_cart, dict):
        raise SomethingWentWrongError

    validated_items = [
        CartItemsReadSchema.model_validate(item)
        for item in purchased_cart.get("cart_items")
    ]

    return CartPurchasedReadSchema(
        cart_id=purchased_cart.get("cart_id", None),
        cart_items=validated_items,
        user_profile=user.user_profile
    )


@router.get("/carts/", response_model=AdminCartsPaginatedSchema)
async def admin_carts_list_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        skip: int = 0,
        limit: int = 20,
        search_user_email: str = None
) -> AdminCartsPaginatedSchema:
    carts_list = await admin_carts_list(
        db=db,
        user_profile=user.user_profile,
        search_by_user_email=search_user_email,
        skip=skip,
        limit=limit
    )

    if not isinstance(carts_list, dict):
        raise SomethingWentWrongError

    return AdminCartsPaginatedSchema(
        total_items=carts_list.get("total_items", 0),
        carts=carts_list.get("carts", [])
    )


@router.get("/carts/{user_cart_id}/", response_model=CartReadSchema)
async def admin_user_cart_endpoint(
        user_cart_id: int,
        db: DpGetDB,
        user: GetCurrentUser
) -> Cart:
    user_cart = admin_user_cart_detail(
        db=db,
        user_profile=user.user_profile,
        user_cart_id=user_cart_id
    )

    if not isinstance(user_cart, Cart):
        raise SomethingWentWrongError

    return user_cart


@router.post("/carts/{user_cart_id}/add_movie/{movie_id}")
async def admin_add_movie_to_users_cart(
        db: DpGetDB,
        user: GetCurrentUser,
        user_cart_id: int,
        movie_id: int
) -> JSONResponse:
    add_item = await cart_add_item(
        db=db,
        user_profile=user.user_profile,
        user_cart_id=user_cart_id,
        movie_id=movie_id
    )

    if not isinstance(add_item, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{add_item.get('detail')}", status_code=status.HTTP_200_OK)


@router.delete("/carts/{user_cart_id}/remove_movie/{movie_id}")
async def admin_remove_movie_from_user_cart(
        db: DpGetDB,
        user: GetCurrentUser,
        user_cart_id: int,
        movie_id: int
) -> JSONResponse:
    deleted_item = await cart_remove_item(
        db=db,
        user_profile=user.user_profile,
        user_cart_id=user_cart_id,
        movie_id=movie_id
    )
    if not isinstance(deleted_item, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{deleted_item.get('detail')}", status_code=status.HTTP_200_OK)
