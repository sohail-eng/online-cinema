from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.cart import Cart
from app.models.user import User, UserProfile


async def get_user_by_email(email, db: AsyncSession) -> User | None:
    result = await db.execute(
        select(User).filter(User.email == email)
        .options(
            joinedload(User.user_group),
            joinedload(User.user_profile).options(
                joinedload(UserProfile.cart).options(
                    selectinload(Cart.cart_items)
                )
            ),
        )
    )
    user = result.scalar_one_or_none()
    return user
