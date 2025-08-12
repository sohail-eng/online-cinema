from datetime import datetime

from fastapi import APIRouter, HTTPException
from starlette import status
from starlette.responses import RedirectResponse, JSONResponse

import crud
import dependencies
import models
import schemas
from exceptions import SomethingWentWrongError

router = APIRouter()


@router.get("/orders/list/", response_model=schemas.OrdersPaginatedSchema)
async def order_list_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        offset: int = 0,
        limit: int = 20
) -> schemas.OrdersPaginatedSchema:

    order_list = await crud.order_list(db=db, user_profile=user.user_profile)
    if not order_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orders were not found")
    if not isinstance(order_list, dict):
        raise SomethingWentWrongError

    return schemas.OrdersPaginatedSchema(
        items=order_list.get("all_orders"),
        offset=offset,
        limit=limit,
        total_items=order_list.get("total_items")
    )


@router.get("/orders/{order_id}/", response_model=schemas.OrderDetailSchema)
async def order_detail_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        order_id: int
) -> models.Order:

    order_detail = await crud.order_detail(
        db=db,
        user_profile=user.user_profile,
        order_id=order_id
    )
    if not isinstance(order_detail, models.Order):
        raise SomethingWentWrongError

    return order_detail


@router.post("/order/create/")
async def create_order_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
) -> RedirectResponse:

    create_order = await crud.create_order(
        db=db,
        user_profile=user.user_profile,
    )
    if not isinstance(create_order, models.Order):
        raise SomethingWentWrongError

    return RedirectResponse(
        url=f"/orders/{create_order.id}/",
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/orders/{order_id}/confirm/")
async def order_confirm_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        order_id: int
) -> RedirectResponse:

    order_confirm = await crud.order_confirm(
        db=db,
        user_profile=user.user_profile,
        order_id=order_id
    )
    if not isinstance(order_confirm, dict):
        raise SomethingWentWrongError

    return RedirectResponse(
        url=f"{order_confirm.get('redirect_to_stripe_url')}",
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.delete("/orders/{order_id}/refuse/")
async def order_refuse_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        order_id: int
) -> JSONResponse:

    order_refuse = await crud.order_refuse(
        db=db,
        user_profile=user.user_profile,
        order_id=order_id
    )
    if not isinstance(order_refuse, dict):
        raise SomethingWentWrongError

    return JSONResponse(
        content=f"{order_refuse.get('detail')}",
        status_code=status.HTTP_200_OK
    )


@router.get("/orders/list/", response_model=schemas.OrderDetailPaginatedSchema)
async def admin_users_order_list_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        user_email: str = None,
        date: datetime = None,
        status: str = None,
        limit: int = 20,
        offset: int = 0
) -> schemas.OrderDetailPaginatedSchema:

    user_orders = await crud.admin_users_order_list(
        db=db,
        user_profile=user.user_profile,
        search_by_user_email=user_email,
        filter_by_date=date,
        filter_by_status=status,
        limit=limit,
        skip=offset
    )

    if not isinstance(user_orders, dict):
        raise SomethingWentWrongError

    return schemas.OrderDetailPaginatedSchema(
        orders=user_orders.get("orders"),
        offset=user_orders.get("offset", 0),
        limit=user_orders.get("limit", 0),
        total_items=user_orders.get("total_items", 0)
    )
