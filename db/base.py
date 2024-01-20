import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

engine = create_engine(f"postgresql+psycopg2://{os.environ['DB_URL']}", echo=False)
Session = sessionmaker(engine)


class Base(DeclarativeBase):
    pass
