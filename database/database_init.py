from typing import Generator

import pydantic
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
from database.config import config

engine = create_async_engine(
    url=config.database_url,
    echo=True,
)

session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> Generator:
    async with session_factory() as session:
        yield session
