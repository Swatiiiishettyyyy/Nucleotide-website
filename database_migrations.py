import logging
from typing import Callable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal
from Member_module.Member_model import Member
from Product_module.Product_model import Category, Product
from Product_module.category_service import get_or_create_default_category

logger = logging.getLogger(__name__)


def _ensure_table(engine: Engine, table_callable: Callable[[Engine], None], table_name: str) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        logger.info("Creating table %s", table_name)
        table_callable(engine)


def _ensure_column(engine: Engine, table: str, column: str, ddl: str) -> None:
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column in columns:
        return

    logger.info("Adding column %s.%s", table, column)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            conn.commit()
    except SQLAlchemyError as exc:
        logger.error("Failed to add column %s.%s: %s", table, column, exc)
        raise


def _backfill_product_categories(session: Session) -> None:
    default_category = get_or_create_default_category(session)
    products = session.query(Product).filter(Product.category_id.is_(None)).all()
    if not products:
        return

    for product in products:
        product.category_id = default_category.id
    session.commit()
    logger.info("Backfilled %s product(s) with default category", len(products))


def _backfill_member_categories(session: Session) -> None:
    members = session.query(Member).filter(Member.associated_category_id.is_(None)).all()
    if not members:
        return

    logger.info("Backfilling %s member(s) with category references", len(members))
    for member in members:
        target_name = member.associated_category or get_or_create_default_category(session).name
        category = (
            session.query(Category)
            .filter(Category.name == target_name)
            .first()
        )
        if not category:
            category = Category(name=target_name)
            session.add(category)
            session.flush()
        member.associated_category_id = category.id
        if not member.associated_category:
            member.associated_category = category.name
    session.commit()


def run_startup_migrations(engine: Engine) -> None:
    """
    Lightweight, idempotent migrations for environments without Alembic.
    Ensures new tables/columns exist and backfills required data.
    """
    # Ensure categories table exists
    Category.__table__.create(bind=engine, checkfirst=True)

    # Ensure new columns exist
    _ensure_column(engine, "products", "category_id", "INT NULL")
    _ensure_column(engine, "members", "dob", "DATE NULL")
    _ensure_column(engine, "members", "associated_category_id", "INT NULL")

    # Backfill data using ORM sessions
    with SessionLocal() as session:
        _backfill_product_categories(session)
        _backfill_member_categories(session)

