import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker


load_dotenv()

engine = create_engine(f"postgresql+psycopg2://{os.environ['DB_URL']}", echo=False)
Session = sessionmaker(engine)

async_engine = create_async_engine(f"postgresql+asyncpg://{os.environ['DB_URL']}", echo=False)
AsyncSession = async_sessionmaker(async_engine)


class Base(DeclarativeBase):
    pass
