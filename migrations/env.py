from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from flask import current_app

config = context.config
if config.config_file_name and os.path.exists(config.config_file_name):
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DATABASE_URL", "sqlite:///elf.db"),
)

target_metadata = current_app.extensions["migrate"].db.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = current_app.extensions["migrate"].db.engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
