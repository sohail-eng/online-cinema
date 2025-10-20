from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from starlette.status import HTTP_404_NOT_FOUND

from app.models.movie import Movie
from app.models.order import Order, OrderItem
from app.models.payment import Payment, PaymentStatusEnum
from app.models.user import UserProfile, User, UserGroupEnum
from app.utils.exceptions import UserDontHavePermissionError, PaymentNotFoundError


async def payments_list(
        db: AsyncSession,
        user_profile: UserProfile,
        skip: int = 0,
        limit: int = 20
):
    result_user_payments = await db.execute(select(Payment).filter(
        Payment.user_profile_id == user_profile.id
    ).offset(skip).limit(limit).options(
        selectinload(Payment.payment_items)
        )
    )
    user_payments = result_user_payments.scalars().all()

    all_user_payments_count = await db.execute(func.count(Payment).filter(
        Payment.user_profile_id == user_profile.id)
    )

    return {"user_payments": user_payments, "total_items": all_user_payments_count}


async def payment_detail_page(
        db: AsyncSession,
        user_profile: UserProfile,
        payment_id: int
):
    result_payment = await db.execute(
        select(Payment)
        .filter(Payment.id == payment_id)
        .options(
            selectinload(Payment.payment_items),
            joinedload(Payment.order).options(
                selectinload(Order.order_items).options(
                    joinedload(OrderItem.movie).options(
                        selectinload(Movie.genres),
                        selectinload(Movie.stars),
                        selectinload(Movie.directors)
                    )
                )
            )
        )
    )
    payment = result_payment.scalar_one_or_none()

    if payment and user_profile.id != payment.user_profile_id:
        raise UserDontHavePermissionError("User dont have permissions to get this payment")

    if not Payment:
        raise PaymentNotFoundError("Payment py provided id was not found")

    return payment


async def admin_payment_user_list(
        db: AsyncSession,
        user_profile: UserProfile,
        skip: int = 0,
        limit: int = 20,
        search_user_email: str = None,
        search_status: str = None,
        date: datetime = None
):
    if user_profile.user.user_group.name == UserGroupEnum.user:
        raise UserDontHavePermissionError("User dont have permissions to visit this page")

    query = select(Payment)

    if search_user_email:
        query = query.join(Payment.user_profile).join(
            UserProfile.user
        ).filter(User.email.ilike(f"%{search_user_email}%"))

    if search_status and (
            search_status == PaymentStatusEnum.successful
            or search_status == PaymentStatusEnum.canceled
            or search_status == PaymentStatusEnum.refunded
    ):
        query = query.filter(Payment.status == search_status)

    if date:
        query = query.filter(Payment.created_at >= date)

    query_with_pagination = query.offset(skip).limit(limit).options(
        joinedload(Payment.user_profile).options(
            joinedload(UserProfile.user)
        )
    )

    result_payments_with_pagination = await db.execute(query_with_pagination)
    payments = result_payments_with_pagination.scalars().all()

    count_of_all_payments = await db.execute(
        select(func.count())
        .select_from(query.subquery())
    )

    if not payments:
        return {"detail_404": "Payments was not found"}

    return {
        "payments": payments,
        "total_items": count_of_all_payments.scalar_one_or_none()
    }


async def admin_user_payment_detail(
        db: AsyncSession,
        user_profile: UserProfile,
        payment_id: int
):
    if user_profile.user.user_group.name == UserGroupEnum.user:
        raise UserDontHavePermissionError("User dont have permissions to visit this page")

    result_payment = await db.execute(
        select(Payment).filter(Payment.id == payment_id)
    )
    if not result_payment:
        raise PaymentNotFoundError("Payment py provided id was not found")

    return result_payment
