"""SQLAlchemy Base and model registry for migrations"""
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.compiler import compiles
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


# Map pgvector Vector type to TEXT when running against SQLite for zero-setup local testing
@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"
