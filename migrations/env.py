import logging
from logging.config import fileConfig
import sys
import os

from alembic import context

# Add project root to path so imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import your Flask app factory and extensions
from app import create_app
from extensions import db
from models import *  # import all your models here so Alembic sees them

# Alembic Config object
config = context.config

# Set up logging
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

# Create Flask app and push app context
flask_app = create_app()
with flask_app.app_context():
    # Use SQLAlchemy metadata from your Flask-SQLAlchemy db
    target_metadata = db.metadata

    # Set the SQLAlchemy URL dynamically
    config.set_main_option("sqlalchemy.url", str(db.engine.url).replace("%", "%%"))

    # Offline migration
    def run_migrations_offline():
        url = config.get_main_option("sqlalchemy.url")
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    # Online migration
    def run_migrations_online():
        connectable = db.engine

        # Prevent empty autogenerate migrations
        def process_revision_directives(context, revision, directives):
            if getattr(config.cmd_opts, "autogenerate", False):
                script = directives[0]
                if script.upgrade_ops.is_empty():
                    directives[:] = []
                    logger.info("No changes in schema detected.")

        conf_args = {"process_revision_directives": process_revision_directives}

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                **conf_args,
            )

            with context.begin_transaction():
                context.run_migrations()

    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
