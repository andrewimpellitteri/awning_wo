import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the parent directory to the path so we can import from the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Flask app and database
from app import create_app
from extensions import db

# Import all models so Alembic can see them
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem
from models.repair_order import RepairWorkOrder, RepairWorkOrderItem
from models.source import Source
from models.inventory import Inventory
from models.user import User
from models.invite_token import InviteToken
from models.work_order_file import WorkOrderFile
from models.repair_order_file import RepairOrderFile
from models.checkin import CheckIn, CheckInItem

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Create Flask app and get database URI from it
# Respect POSTGRES_DB environment variable for switching between databases
app = create_app()
db_uri = app.config['SQLALCHEMY_DATABASE_URI']

# Override database name if POSTGRES_DB is set (for test/prod switching)
postgres_db_override = os.environ.get('POSTGRES_DB')
if postgres_db_override:
    # Parse the URI and replace the database name
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(db_uri)
    # Replace the database name (path without leading /)
    new_path = f'/{postgres_db_override}'
    db_uri = urlunparse((parsed.scheme, parsed.netloc, new_path, parsed.params, parsed.query, parsed.fragment))

config.set_main_option('sqlalchemy.url', db_uri)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = db.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
