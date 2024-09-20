from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, database_url: str | None = None) -> None:
        if database_url is None:
            database_url = "sqlite+aiosqlite://"

        self.engine = create_async_engine(database_url, echo=True)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialise_database(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
