from collections import Counter
from datetime import datetime
from typing import Annotated

import stripe
from fastapi import APIRouter, HTTPException, Request, Header
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload, joinedload
from starlette import status

from app.core.settings import settings
from app.crud.payment import payments_list, payment_detail_page, admin_payment_user_list, admin_user_payment_detail
from app.models.movie import Movie
from app.models.order import OrderItem, Order, OrderStatusEnum
from app.models.payment import Payment, PaymentStatusEnum, PaymentItem
from app.schemas.payment import PaginatedUserPaymentList, UserPaymentDetailSchema, PaginatedAdminPaymentList, \
    AdminPaginatedList, AdminPaymentDetailSchema
from app.utils.dependencies import DpGetDB, GetCurrentUser
from app.utils.exceptions import OrderDoesNotExistError, SomethingWentWrongError

router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/stripe/webhook/")
async def stripe_webhook_endpoint(
        db: DpGetDB,
        request: Request,
        stipe_signature: Annotated[str, Header()]
):
    payload = await request.body()
    webhook_secret = settings.STRIPE_SECRET_KEY

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stipe_signature,
            secret=webhook_secret
        )
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature was provided")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload was provided")

    chk_cmpltd = "checkout.session.completed"
    pmt_faild = "payment_intent.payment_failed"
    rfnded = "charge.refunded"

    if event["type"] == chk_cmpltd\
            or event["type"] == pmt_faild\
            or event["type"] == rfnded:

        session = event["data"]["object"]

        order_id = session["metadata"]["order_id"]
        user_profile_id = session["metadata"]["order_id"]
        total_amount = session["metadata"]["total_amount"]

        result_order_items = await db.execute(
            select(OrderItem.id)
            .filter(OrderItem.order_id == order_id)
            .options(
                joinedload(OrderItem.movie)
            )
        )
        all_order_items_ids = result_order_items.scalars().all()

        result_order = await db.execute(select(Order).filter(Order.id == order_id))
        order = result_order.scalar_one_or_none()

        new_payment_obj = Payment(
            user_profile_id=user_profile_id,
            order_id=order_id,
            amount=total_amount,
            external_payment_id=event["id"]
        )

        if event["type"] == chk_cmpltd:
            new_payment_obj.status = PaymentStatusEnum.successful
            order.status = OrderStatusEnum.paid

        elif event["type"] == pmt_faild:
            new_payment_obj.status = PaymentStatusEnum.canceled
            order.status = OrderStatusEnum.canceled

        elif event["type"] == rfnded:
            new_payment_obj.status = PaymentStatusEnum.refunded
            order.status = OrderStatusEnum.canceled

        await db.commit()
        await db.refresh(new_payment_obj)

        payment_items = [PaymentItem(
            payment_id=new_payment_obj.id,
            order_item_id=item.id,
            price_at_payment=item.movie.price
        ) for item in all_order_items_ids]

        db.add_all(payment_items)
        await db.commit()
        print(f"payment and payment_items for {order_id} is successfully created")


@router.post("/stripe/create_checkout_session/{order_id}/")
async def stripe_checkout_session(
        db: DpGetDB,
        user: GetCurrentUser,
        order_id: int
):
    result_order = await db.execute(
        select(Order)
        .join(Order.order_items)
        .filter(
            Order.id == order_id,
            ~Order.id.in_(
                select(Payment.order_id)
                .filter(Payment.status == PaymentStatusEnum.successful)
            ),
            ~OrderItem.id.in_(
                select(PaymentItem.order_item_id)
                .join(PaymentItem.payment)
                .filter(Payment.status == PaymentStatusEnum.successful)
            )
        )
        .options(
            selectinload(Order.order_items),
            joinedload(OrderItem.movie)
        )
    )
    order = result_order.scalar_one_or_none()
    if not order:
        raise OrderDoesNotExistError

    result_order_movies_ids = await db.execute(
        select(OrderItem.movie_id)
        .filter(OrderItem.order_id == order.id)
    )
    order_movies_ids = result_order_movies_ids.scalars().all()

    if not order_movies_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movies from provided order_id wasn't found."
        )

    result_existing_movies = await db.execute(
        select(Movie.id)
        .filter(Movie.id.in_(order_movies_ids))
    )
    existing_movies_ids = result_existing_movies.scalars().all()

    if order_movies_ids != existing_movies_ids:
        outer_ids = [i for i in order_movies_ids if i not in set(existing_movies_ids)]
        await db.execute(
            delete(OrderItem)
            .filter(OrderItem.id.in_(outer_ids))
        )
        await db.commit()
        await db.refresh(order.order_items)

    dict_with_all_movies = Counter(order_movies_ids)

    movie_ids_to_delete_from_users_order_items = []
    for k, v in dict_with_all_movies.items():
        if v > 1:
            movie_ids_to_delete_from_users_order_items.append(k)

    if movie_ids_to_delete_from_users_order_items:
        await db.execute(delete(OrderItem).filter(
            OrderItem.id.in_(movie_ids_to_delete_from_users_order_items))
        )
        await db.commit()
        await db.refresh(order.order_items)

    result_users_bought_movies = await db.execute(
        select(PaymentItem.order_item.movie_id)
        .join(PaymentItem.order_item)
        .join(PaymentItem.payment)
        .filter(Payment.status == PaymentStatusEnum.successful)
    )
    users_bought_movies = result_users_bought_movies.scalars().all()

    movie_ids_to_delete_that_user_bought = []
    for i in order_movies_ids:
        if i in users_bought_movies:
            movie_ids_to_delete_that_user_bought.append(i)

    if movie_ids_to_delete_that_user_bought:
        await db.execute(
            delete(OrderItem)
            .filter(
                OrderItem.movie_id.in_(movie_ids_to_delete_that_user_bought),
                OrderItem.order_id.in_(
                    select(Order.id).filter(
                        Order.user_profile_id == user.user_profile.id
                    )
                ),
                ~OrderItem.id.in_(
                    select(PaymentItem.order_item_id)
                    .join(PaymentItem.payment)
                    .filter(
                        Payment.status == PaymentStatusEnum.successful,
                        Payment.user_profile_id == user.user_profile.id
                    )
                )
            )
        )
        await db.commit()
        await db.refresh(order.order_items)

    movie_names = [f"{num+1}: {item.movie.name}" for num, item in enumerate(order)]
    correct_order_names = (
        f"Order-nummer: {order.id}\n"
        f"Count of movies to buy: {len(order.order_items)}\n"
        f"Movie names: {'\n'.join(movie_names)}"
        f"User: {user.user_profile.id}"
    )
    print(correct_order_names)

    total_order_price_from_db = order.total_amount
    total_price_from_order_items = sum([i.movie.price for i in order])
    if total_order_price_from_db != total_price_from_order_items:
        order.total_amount = total_price_from_order_items
        await db.commit()
        await db.refresh(order)

    line_items = []
    for item in order.order_items:
        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": item.movie.name,
                },
                "unit_amount": int(item.movie.price * 100),
            },
            "quantity": 1,
        })

    if not line_items:
        raise HTTPException(status_code=400, detail="Order is empty.")

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=line_items,
            mode="payment",
            success_url=f"https://{settings.HOST}/payment/success_pay",
            cancel_url=f"https://{settings.HOST}/payment/cancel_pay",
            metadata={
                "user_profile_id": user.user_profile.id,
                "order_id": order.id,
                "total_amount": order.total_amount,
            }
        )
        return {"stripe_payment_url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



@router.get("payments/list/", response_model=PaginatedUserPaymentList)
async def payments_list_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        skip: int = 0,
        limit: int = 20
):
    result_payments_list = await payments_list(
        db=db,
        user_profile=user.user_profile,
        skip=skip,
        limit=limit
    )
    if not isinstance(result_payments_list, dict):
        raise SomethingWentWrongError

    return PaginatedUserPaymentList(
        payments=result_payments_list.get("user_payments"),
        total_items=result_payments_list.get("total_items")
    )

@router.get("payments/{payment_id}/", response_model=UserPaymentDetailSchema)
async def payment_detail_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        payment_id: int
):
    result_detail_payment = await payment_detail_page(
        db=db,
        user_profile=user.user_profile,
        payment_id=payment_id
    )

    if not isinstance(result_detail_payment, Payment):
        raise SomethingWentWrongError

    return result_detail_payment


@router.get("/admin/user_payments/list", response_model=AdminPaginatedList)
async def admin_user_payments_list_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        user_email: str = None,
        date: datetime = None,
        status: str = None,
        skip: int = 0,
        limit: int = 20
):
    result_admin_payment_user_list = await admin_payment_user_list(
        db=db,
        user_profile=user.user_profile,
        skip=skip,
        limit=limit,
        search_user_email=user_email,
        date=date,
        search_status=status
    )

    if not isinstance(result_admin_payment_user_list, dict):
        raise SomethingWentWrongError

    if result_admin_payment_user_list.get("detail_404"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result_admin_payment_user_list.get("detail_404")
        )

    return AdminPaginatedList(
        payments=result_admin_payment_user_list.get("payments"),
        total_items=result_admin_payment_user_list.get("total_items", 0)
    )


@router.get("/admin/user_payments/{payment_id}/", response_model=AdminPaymentDetailSchema)
async def admin_user_payment_detail_endpoint(
        db: DpGetDB,
        user: GetCurrentUser,
        payment_id: int
):
    result_admin_user_payment = await admin_user_payment_detail(
        db=db,
        user_profile=user.user_profile,
        payment_id=payment_id
    )

    if not isinstance(result_admin_user_payment, Payment):
        raise SomethingWentWrongError

    return result_admin_user_payment
