from sqlalchemy import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, database_name: str | None = None) -> None:
        database_url = URL.create("sqlite+aiosqlite", database=database_name)

        self.engine = create_async_engine(database_url)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialise_database(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
