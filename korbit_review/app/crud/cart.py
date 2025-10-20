from typing import Any, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.cart import Cart, CartItem
from app.models.movie import Movie
from app.models.order import OrderItem, OrderStatusEnum, Order
from app.models.payment import PaymentItem, Payment, PaymentStatusEnum
from app.models.user import UserProfile, UserGroupEnum, User
from app.utils.exceptions import MovieNotFoundError, UserDontHavePermissionError, MovieAlreadyIsPurchasedOrInCartError, \
    SomethingWentWrongError, CartNotExistError


async def cart_add_item(
        db: AsyncSession,
        user_profile: UserProfile,
        movie_id: int,
        user_cart_id: int = None,
) -> MovieNotFoundError | UserDontHavePermissionError | dict[str, str]:
    result_movie = await db.execute(
        select(Movie)
        .filter(Movie.id == movie_id)
    )
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")

    if not user_profile.cart:
        new_cart = Cart(user_profile_id=user_profile.id)
        db.add(new_cart)
        await db.commit()
        await db.refresh(new_cart)

    try:
        if user_profile.user.user_group.name == UserGroupEnum.user:
            cart = user_profile.cart
        else:
            if user_profile.user.user_group.name == UserGroupEnum.user:
                raise UserDontHavePermissionError("User have not permissions to add items to other user's carts")

            result_user_cart = await db.execute(
                select(Cart)
                .filter(Cart.id == user_cart_id)
            )
            cart = result_user_cart.scalar_one_or_none()

        all_movies_in_users_cart = [c.movie_id for c in cart.cart_items]
        result_all_purchased_movies_ids = await db.execute(
            select(OrderItem.movie_id)
            .join(OrderItem.order)
            .filter(
                OrderItem.order_id.in_(
                    select(Order.id)
                    .filter(
                        Order.user_profile_id == user_profile.id,
                        Order.status == OrderStatusEnum.paid,
                        Order.id.in_(
                            select(Payment.order_id)
                            .filter(
                                Payment.user_profile_id == user_profile.id,
                                Payment.status == PaymentStatusEnum.successful,
                            )
                        )
                    )
                ),
            ),
            CartItem.cart.has(
                Cart.user_profile_id == cart.user_profile_id
            )
        )
        all_purchased_movies_ids = result_all_purchased_movies_ids.scalars().all()

        if movie.id in all_movies_in_users_cart or movie.id in all_purchased_movies_ids:
            raise MovieAlreadyIsPurchasedOrInCartError("Movie is already purchased or in user's cart")

        new_cart_item = CartItem(cart_id=cart.id, movie_id=movie.id)
        db.add(new_cart_item)
        await db.commit()
        await db.refresh(new_cart_item)
        return {"detail": "Item was successfully added"}

    except Exception as e:
        await db.rollback()
        raise e


async def cart_remove_item(
        db: AsyncSession,
        user_profile: UserProfile,
        movie_id: int,
        user_cart_id: int = None
) -> Exception | MovieNotFoundError | dict[str, str]:
    result_movie = await db.execute(
        select(Movie)
        .filter(Movie.id == movie_id)
    )
    movie = result_movie.scalar_one_or_none()

    if not movie:
        raise MovieNotFoundError("Movie was not found")

    if not user_cart_id:
        result_user_cart_item = await db.execute(
            select(CartItem)
            .filter(
                CartItem.movie_id == movie.id,
                CartItem.cart.has(
                    Cart.user_profile_id == user_profile.id
                )
            )
        )
    else:
        if user_profile.user.user_group.name == UserGroupEnum.user:
            raise UserDontHavePermissionError(
                "User have not permissions to delete items from other user's carts"
            )
        result_user_cart_item = await db.execute(
            select(CartItem)
            .filter(
                CartItem.movie_id == movie.id,
                CartItem.cart.has(
                    Cart.id == user_cart_id,
                )
            )
        )

    user_cart_item = result_user_cart_item.scalar_one_or_none()

    if not user_cart_item:
        raise SomethingWentWrongError("User has not this movie in cart")

    try:
        await db.delete(user_cart_item)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e

    return {"detail": "Movie was successfully deleted from user's cart"}


async def cart_items_list(
        db: AsyncSession,
        user_profile: UserProfile,
        search_by_book_name: str = None
) -> dict[str, int | None | Cart | Any]:
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

    options_subquery = selectinload(Cart.cart_items).options(
        joinedload(CartItem.movie).options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
            joinedload(Movie.certification)
        )
    )

    if not search_by_book_name:
        query = (
            select(Cart)
            .filter(
                Cart.user_profile_id == user_profile.id,
                Cart.cart_items.any(
                    is_paid_by_order_subquery,
                    is_paid_by_payment_subquery
                )
            ).options(
                options_subquery
            )
        )
    else:
        query = select(Cart).filter(
            Cart.user_profile_id == user_profile.id,
            Cart.cart_items.any(
                CartItem.movie.has(
                    Movie.name.ilike(f"%{search_by_book_name}%")
                ),
                is_paid_by_order_subquery,
                is_paid_by_payment_subquery
            )
        ).options(
            options_subquery
        )

    result_cart = await db.execute(query)
    cart = result_cart.scalar_one_or_none()

    result_total_price = await db.execute(
        select(func.sum(Movie.price))
        .select_from(CartItem)
        .join(CartItem.cart)
        .join(CartItem.movie)
        .filter(Cart.user_profile_id == user_profile.id)
    )

    total_price = result_total_price.scalar_one_or_none()

    return {
        "cart_id": cart.id,
        "cart_items": cart.cart_items,
        "total_price": total_price or 0,
    }


async def cart_purchased_items(
        db: AsyncSession,
        user_profile: UserProfile,
        search_by_book_name: str = None
) -> dict[str, int | None | Any]:
    is_paid_by_order_subquery = CartItem.movie_id.in_(
        select(OrderItem.movie_id)
        .join(OrderItem.order)
        .filter(
            Order.user_profile_id == user_profile.id,
            Order.status == OrderStatusEnum.paid
        )
    )

    is_paid_by_payment_subquery = CartItem.movie_id.in_(
        select(OrderItem.movie_id)
        .join(OrderItem.order)
        .filter(
            Order.id.in_(
                select(Payment.order_id)
                .filter(Payment.status == PaymentStatusEnum.successful)
            )
        )
    )

    options_subquery = selectinload(Cart.cart_items).options(
        joinedload(CartItem.movie).options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
            joinedload(Movie.certification)
        )
    )

    if not search_by_book_name:
        query = select(Cart).filter(
            Cart.user_profile_id == user_profile.id,
            Cart.cart_items.any(
                is_paid_by_order_subquery,
                is_paid_by_payment_subquery
            )
        ).options(
            options_subquery
        )
    else:
        query = select(Cart).filter(
            Cart.user_profile_id == user_profile.id,
            Cart.cart_items.has(
                CartItem.movie.any(
                    Movie.name.ilike(f"%{search_by_book_name}%"),
                    is_paid_by_order_subquery,
                    is_paid_by_payment_subquery
                ),
            )
        ).options(
            options_subquery
        )

    result_cart = await db.execute(query)
    cart = result_cart.scalar_one_or_none()
    return {
        "cart_id": cart.id,
        "cart_items": cart.cart_items
    }


async def admin_carts_list(
        db: AsyncSession,
        user_profile: UserProfile,
        search_by_user_email: str = None,
        skip: int = 0,
        limit: int = 20
) -> Sequence[Cart]:
    if user_profile.user.user_group.name == UserGroupEnum.user:
        raise UserDontHavePermissionError("Users have not permissions to visit this page.")

    if search_by_user_email:
        query = select(Cart).filter(
            Cart.user_profile.has(
                UserProfile.user.has(
                    User.email == search_by_user_email
                ))
        ).options(
            selectinload(Cart.cart_items),
            joinedload(Cart.user_profile).options(
                joinedload(UserProfile.user)
            )
        ).offset(skip=skip).limit(limit=limit)
    else:
        query = select(Cart).options(
            selectinload(Cart.cart_items),
            joinedload(Cart.user_profile).options(
                joinedload(UserProfile.user)
            )
        ).offset(skip=skip).limit(limit=limit)

    result_carts = await db.execute(query)
    carts = result_carts.scalars().all()

    result_count_of_all_carts = await db.execute(func.count(Cart.id))
    return {
        "carts": carts,
        "total_items": result_count_of_all_carts.scalar_one_or_none()
    }


async def admin_user_cart_detail(
        db: AsyncSession,
        user_profile: UserProfile,
        user_cart_id: int,
):
    if user_profile.user.user_group.name == UserGroupEnum.user:
        raise UserDontHavePermissionError

    result_cart = await db.execute(select(Cart).filter(Cart.id == user_cart_id).options(
        selectinload(Cart.cart_items).options(
            joinedload(CartItem.movie).options(
                selectinload(Movie.genres),
                selectinload(Movie.stars),
                selectinload(Movie.directors),
                joinedload(Movie.certification)
            ),
        ),
        joinedload(Cart.user_profile).options(
            joinedload(UserProfile.user)
        )
    ))
    cart = result_cart.scalar_one_or_none()

    if not cart:
        raise CartNotExistError("Cart by provided id does not exists")

    return cart
