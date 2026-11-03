"""Models and migrations must always agree.

If a model changes without a new migration, `command.check` fails here, so the
commit history can never contain a schema that the migrations cannot build.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import get_settings


@pytest.fixture()
def alembic_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Config]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'migration.db'}")
    get_settings.cache_clear()
    yield Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    get_settings.cache_clear()


def test_migrations_build_a_schema_that_matches_the_models(alembic_config: Config):
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)  # raises if the models have unmigrated changes


def test_migrations_can_be_reversed(alembic_config: Config):
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
