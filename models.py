from typing import List, Optional
import os
from datetime import datetime, date
import asyncio
import enum

from sqlalchemy import String, Text, Boolean, DateTime, func, ForeignKey, create_engine, Enum, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv


load_dotenv()

engine = create_async_engine(
    os.getenv("SQLALCHEMY_URI"),
    echo=True,
    pool_pre_ping=True,  # Перевіряє життєздатність з'єднання перед використанням
)

# Фабрика для створення сесій
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, # Важливо для asyncio, щоб об'єкти не "падали" після commit
)


class Status(enum.Enum):
    in_progress = "In progress"
    done = "Done"
    qc = "QC"
    accepted = "Accepted"
    running = "Running"


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, index=True)


class AgentModel(Base):
    __tablename__ = "agent"

    agent_id: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(100))
    source_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.in_progress)
    done: Mapped[bool] = mapped_column(Boolean(), default=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date(), default=None)
    code: Mapped[Optional[str]] = mapped_column(Text(), default=None)
    count_emit: Mapped[Optional[int]] = mapped_column(default=None)
    create_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    update_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(create_db())