"""Seed command.

    python -m app.seed            seed an empty database (does nothing if data exists)
    python -m app.seed --reset    delete everything, then seed again

Safe to run on every deploy: without --reset it never touches existing data.
"""

import argparse
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.db import get_session_factory
from app.models import Base, Order, Outlet, User
from app.seed.catalog import seed_catalog
from app.seed.demo import seed_orders, seed_users


def reset_database(db: Session) -> None:
    """Delete every row, children before parents."""
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())


def seed_all(db: Session, now: datetime | None = None, password: str | None = None) -> None:
    now = now or utcnow()
    password = password or get_settings().demo_password
    seed_catalog(db)
    users = seed_users(db, now, password)
    seed_orders(db, now, users)


def main(
    argv: Sequence[str] | None = None, factory: sessionmaker[Session] | None = None
) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed", description=__doc__)
    parser.add_argument("--reset", action="store_true", help="delete all data, then seed")
    parser.add_argument(
        "--force", action="store_true", help="allow --reset when ENV=production"
    )
    args = parser.parse_args(argv)

    if args.reset and get_settings().is_production and not args.force:
        print("Refusing to reset a production database without --force.")
        return 2

    with (factory or get_session_factory())() as db:
        has_data = db.scalar(select(func.count()).select_from(Outlet)) > 0
        if has_data and not args.reset:
            print("Database already contains data; nothing seeded. Use --reset to rebuild it.")
            return 0
        if args.reset:
            reset_database(db)
        seed_all(db)
        db.commit()

        outlets = db.scalar(select(func.count()).select_from(Outlet))
        users = db.scalar(select(func.count()).select_from(User))
        orders = db.scalar(select(func.count()).select_from(Order))
    print(f"Seeded {outlets} outlets, {users} demo users and {orders} sample orders.")
    return 0
