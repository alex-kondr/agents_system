from typing import List, Optional
import os
from datetime import datetime

from sqlalchemy import String, Text, Boolean, DateTime, func, ForeignKey, create_engine
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase, sessionmaker
from dotenv import load_dotenv


load_dotenv()
engine = create_engine(os.getenv("SQLALCHEMY_URI"), echo=True)
Session = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, index=True)


class AgentModel(Base):
    __tablename__ = "agent"

    done: Mapped[bool] = mapped_column(Boolean(), default=False)
    create_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
    update_at: Mapped[datetime] = mapped_column(DateTime(), onupdate=datetime.now())
    agent_id: Mapped[str] = mapped_column(String(10))
    code: Mapped[Optional[str]] = mapped_column(Text(), default=None)
    count_emit: Mapped[Optional[int]] = mapped_column(default=None)


Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)