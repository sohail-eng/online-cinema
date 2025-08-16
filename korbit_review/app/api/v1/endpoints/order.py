from datetime import datetime

from fastapi import APIRouter, HTTPException
from starlette import status
from starlette.responses import RedirectResponse, JSONResponse

from app.crud.order import order_detail as order_detail_page, order_list as order_list_page, create_order, \
    order_confirm, order_refuse, admin_users_order_list
from app.models.order import Order
from app.schemas.order import OrdersPaginatedSchema, OrderDetailSchema, OrderDetailPaginatedSchema
from app.utils.dependencies import DpGetDB, GetCurrentUser
from app.utils.exceptions import SomethingWentWrongError

router = APIRouter()


@router.get("/orders/list/", response_model=OrdersPaginatedSchema)
async def order_list_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        offset: int = 0,
        limit: int = 20
) -> OrdersPaginatedSchema:

    order_list = await order_list_page(db=db, user_profile=user.user_profile)
    if not order_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orders were not found")
    if not isinstance(order_list, dict):
        raise SomethingWentWrongError

    return OrdersPaginatedSchema(
        items=order_list.get("all_orders"),
        offset=offset,
        limit=limit,
        total_items=order_list.get("total_items")
    )


@router.get("/orders/{order_id}/", response_model=OrderDetailSchema)
async def order_detail_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        order_id: int
) -> Order:

    order_detail = await order_detail_page(
        db=db,
        user_profile=user.user_profile,
        order_id=order_id
    )
    if not isinstance(order_detail, Order):
        raise SomethingWentWrongError

    return order_detail


@router.post("/order/create/")
async def create_order_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
) -> RedirectResponse:

    create_order_ = await create_order(
        db=db,
        user_profile=user.user_profile,
    )
    if not isinstance(create_order_, Order):
        raise SomethingWentWrongError

    return RedirectResponse(
        url=f"/orders/{create_order_.id}/",
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/orders/{order_id}/confirm/")
async def order_confirm_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        order_id: int
) -> RedirectResponse:

    order_confirm_ = await order_confirm(
        db=db,
        user_profile=user.user_profile,
        order_id=order_id
    )
    if not isinstance(order_confirm_, dict):
        raise SomethingWentWrongError

    return RedirectResponse(
        url=f"{order_confirm_.get('redirect_to_stripe_url')}",
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.delete("/orders/{order_id}/refuse/")
async def order_refuse_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        order_id: int
) -> JSONResponse:

    order_refuse_ = await order_refuse(
        db=db,
        user_profile=user.user_profile,
        order_id=order_id
    )
    if not isinstance(order_refuse_, dict):
        raise SomethingWentWrongError

    return JSONResponse(
        content=f"{order_refuse_.get('detail')}",
        status_code=status.HTTP_200_OK
    )


@router.get("/orders/list/", response_model=OrderDetailPaginatedSchema)
async def admin_users_order_list_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        user_email: str = None,
        date: datetime = None,
        status: str = None,
        limit: int = 20,
        offset: int = 0
) -> OrderDetailPaginatedSchema:

    user_orders = await admin_users_order_list(
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

    return OrderDetailPaginatedSchema(
        orders=user_orders.get("orders"),
        offset=user_orders.get("offset", 0),
        limit=user_orders.get("limit", 0),
        total_items=user_orders.get("total_items", 0)
    )
