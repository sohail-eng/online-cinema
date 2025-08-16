from datetime import datetime
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.cart import CartItem, Cart
from app.models.movie import Movie
from app.models.order import Order, OrderItem, OrderStatusEnum
from app.models.payment import Payment, PaymentStatusEnum
from app.models.user import UserProfile, UserGroupEnum
from app.utils.exceptions import OrderDoesNotExistError, UserDontHavePermissionError


async def order_list(
        db: AsyncSession,
        user_profile: UserProfile,
        offset: int = 0,
        limit: int = 20
) -> Sequence[Order]:
    result_all_orders = await db.execute(select(Order).filter(
        Order.user_profile_id == user_profile.id).options(
        joinedload(Order.user_profile).options(
            joinedload(UserProfile.user)
        ),
        selectinload(Order.order_items).options(
            joinedload(OrderItem.movie).options(
                selectinload(Movie.genres),
                selectinload(Movie.stars),
                selectinload(Movie.directors)
            )
        )
    ).offset(offset).limit(limit))

    all_orders = result_all_orders.scalars().all()

    total_items = await db.execute(
        func.count(Order)
        .filter(Order.user_profile_id == user_profile.id)
    )

    return {"all_orders": all_orders, "total_items": total_items.scalar_one_or_none()}


async def order_detail(
        db: AsyncSession,
        user_profile: UserProfile,
        order_id: int
) -> Order | OrderDoesNotExistError:
    result_order = await db.execute(select(Order).filter(
        Order.id == order_id,
        Order.user_profile_id == user_profile.id).options(
        joinedload(Order.user_profile).options(
            joinedload(UserProfile.user)
        ),
        selectinload(Order.order_items).options(
            joinedload(OrderItem.movie).options(
                selectinload(Movie.genres),
                selectinload(Movie.directors),
                selectinload(Movie.stars)
            )
        )

    )
    )
    order = result_order.scalar_one_or_none()

    if not order:
        raise OrderDoesNotExistError("Order was not found")

    return order


async def create_order(
        db: AsyncSession,
        user_profile: UserProfile,
) -> Order | Exception:
    is_paid_by_order_subquery = ~CartItem.movie_id.in_(
        select(OrderItem.movie_id)
        .join(OrderItem.order)
        .filter(
            Order.user_profile_id == user_profile.id,
            Order.status == OrderStatusEnum.paid
        )
    )

    is_paid_by_payment_subquery = ~CartItem.movie_id.in_(
        select(OrderItem.movie_id)
        .join(OrderItem.order)
        .filter(
            Order.id.in_(
                select(Payment.order_id)
                .filter(Payment.status == PaymentStatusEnum.successful)
            )
        )
    )

    result_user_items_price = await db.execute(
        select(func.sum(Movie.price))
        .select_from(CartItem)
        .join(CartItem.movie)
        .join(CartItem.cart)
        .filter(Cart.user_profile_id == user_profile.id)
    )
    result_user_items = await db.execute(select(CartItem).filter(
        CartItem.cart.has(
            Cart.user_profile_id == user_profile.id,
        ),
        is_paid_by_order_subquery,
        is_paid_by_payment_subquery
    ).options(
        joinedload(CartItem.movie)
        )
    )
    user_items = result_user_items.scalars().all()
    total_amount = result_user_items_price.scalar_one_or_none() or 0.00
    try:
        new_order = Order(
            user_profile_id=user_profile.id,
            total_amount=total_amount
        )
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)

        order_items = [OrderItem(
            order_id=new_order.id,
            movie_id=item.movie_id,
            price_at_order=item.movie.price
        ) for item in user_items]

        if order_items:
            db.add_all(order_items)
            await db.commit()

        return new_order
    except Exception as e:
        await db.rollback()
        raise e


async def order_confirm(
        db: AsyncSession,
        user_profile: UserProfile,
        order_id: int
) -> OrderDoesNotExistError | dict[str, str]:
    result_order = await db.execute(select(Order).filter(
        Order.id == order_id,
        Order.user_profile_id == user_profile.id)
    )
    order = result_order.scalar_one_or_none()

    if not order:
        raise OrderDoesNotExistError("Order by provided id does not exists")

    ### LOGIC STRIPE
    return {"detail": "redirect_to_stripe_url"}


async def order_refuse(
        db: AsyncSession,
        user_profile: UserProfile,
        order_id: int
) -> dict[str, str] | Exception | OrderDoesNotExistError:

    result_order = await db.execute(select(Order).filter(
        Order.id == order_id,
        Order.user_profile_id == user_profile.id
        )
    )
    order_to_delete = result_order.scalar_one_or_none()

    if not order_to_delete:
        raise OrderDoesNotExistError("Order by py provided id does not exists")
    try:
        await db.delete(order_to_delete)
        await db.commit()
        return {"detail": "Order was successfully deleted."}
    except Exception as e:
        await db.rollback()
        raise e


async def admin_users_order_list(
        db: AsyncSession,
        user_profile: UserProfile,
        search_by_user_email: str = None,
        filter_by_date: datetime = None,
        filter_by_status: str = None,
        limit: int = 20,
        skip: int = 0
) -> Sequence[Order] | UserDontHavePermissionError:

    if user_profile.user.user_group.name == UserGroupEnum.user:
        raise UserDontHavePermissionError("User dont have permissions to visit this page")

    query = select(Order)

    if search_by_user_email:
        query = query.join(
            Order.user_profile
        ).filter(UserProfile.user.email.ilike(f"%{search_by_user_email}%"))

    if filter_by_date:
        query = query.filter(Order.created_at >= filter_by_date)

    if filter_by_status and (
            filter_by_status == OrderStatusEnum.pending
            or filter_by_status == OrderStatusEnum.canceled
            or filter_by_status == OrderStatusEnum.paid
    ):
        query = query.filter(Order.status == filter_by_status)
    query = query.options(
        joinedload(Order.user_profile).options(
            joinedload(UserProfile.user)
        ),
        selectinload(Order.order_items).options(
            joinedload(OrderItem.movie).options(
                selectinload(Movie.genres),
                selectinload(Movie.stars),
                selectinload(Movie.directors)
            )
        )
    ).offset(skip).limit(limit)

    result_orders = await db.execute(query)
    orders = result_orders.scalars().all()

    count_orders = await db.execute(func.count(Order))

    return {
        "orders": orders,
        "offset": skip,
        "limit": limit,
        "total_items": count_orders
    }