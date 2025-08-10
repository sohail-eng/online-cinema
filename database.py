from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from settings import settings

SQLALCHEMY_URL = settings.DATABASE_URL

engine = create_async_engine(SQLALCHEMY_URL, echo=True)

SessionLocal = async_sessionmaker(autoflush=False, expire_on_commit=False, bind=engine, class_=AsyncSession)

async def get_db():
    async with SessionLocal() as session:
        yield session
