import os
from psycopg_pool import AsyncConnectionPool
from typing import AsyncGenerator, Any, cast, AsyncIterator
from fastapi import Request
from contextlib import asynccontextmanager
from fastapi import FastAPI

db_port = os.environ.get("DB_PORT")
if db_port is None:
    print("missing env var: DB_PORT")
    raise ValueError

db_host = os.environ.get("DB_HOST")
if db_host is None:
    print("missing env var: DB_HOST")
    raise ValueError

db_pass = os.environ.get("DB_PASS")
if db_pass is None:
    print("missing env var: DB_PASS")
    raise ValueError

db_user = os.environ.get("DB_USER")
if db_user is None:
    print("missing env var: DB_USER")
    raise ValueError

db_name = os.environ.get("DB_NAME")
if db_name is None:
    print("missing env var: DB_NAME")
    raise ValueError


db_conn_str = f"dbname={db_name} user={db_user} password={db_pass} host={db_host} port={db_port}"


def get_db_connection_pool() -> AsyncConnectionPool:
    """
    connection pool
    opened from lifespan
    """
    return AsyncConnectionPool(conninfo=db_conn_str, open=False)


async def db_conn(request: Request) -> AsyncGenerator[Any, Any]:

    db_pool = cast(AsyncConnectionPool, request.state.db_pool)
    async with db_pool.connection() as conn:
        yield conn


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    lifecycle management for the database connection pool
    """
    db_pool = get_db_connection_pool()
    await db_pool.open()

    yield {"db_pool": db_pool}

    # Shutdown events
    await db_pool.close()
