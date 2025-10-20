from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.settings import settings

SQLALCHEMY_URL = settings.DATABASE_URL

engine = create_async_engine(SQLALCHEMY_URL, echo=True)

SessionLocal = async_sessionmaker(autoflush=False, expire_on_commit=False, bind=engine, class_=AsyncSession)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

Base = declarative_base()
