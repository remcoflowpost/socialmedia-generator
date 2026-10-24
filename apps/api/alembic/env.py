from logging.config import fileConfig

from alembic import context
from app import models  # noqa: F401  registreert alle tabellen
from app.db import Base, engine

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)


def run_migrations() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
