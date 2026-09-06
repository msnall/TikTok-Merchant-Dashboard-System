from alembic import context
from app.db import Base
from app import models
target_metadata = Base.metadata
config = context.config
def run_migrations_online():
    from sqlalchemy import engine_from_config, pool
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction(): context.run_migrations()
if context.is_offline_mode(): raise RuntimeError("Offline migrations are not configured")
else: run_migrations_online()

