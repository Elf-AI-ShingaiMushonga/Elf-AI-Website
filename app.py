from __future__ import annotations

import logging
import os
import secrets
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from flask import Flask
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

from flask_mail import Mail

from models import db, setup_database
from extensions import mail


def _normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def configure_logging(app: Flask) -> None:
    if app.debug or app.testing:
        return
    log_dir = os.path.join(app.instance_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "elf-ai.log")
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


migrate = Migrate()


def create_app(config_name: str | None = None) -> Flask:
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)

    app.config.from_object("config.BaseConfig")
    app_env = (config_name or os.getenv("APP_ENV", "development")).lower()
    if app_env == "production":
        app.config.from_object("config.ProductionConfig")
    elif app_env == "testing":
        app.config.from_object("config.TestingConfig")
    else:
        app.config.from_object("config.DevelopmentConfig")

    secret_key = os.getenv("SECRET_KEY")
    if app_env == "production" and (not secret_key or secret_key.lower() == "change-me"):
        raise RuntimeError("SECRET_KEY must be set to a secure value in production.")
    app.config["SECRET_KEY"] = secret_key or secrets.token_hex(32)

    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))

    # WorkMail uses SSL, not TLS
    app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'True') == 'True'
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'False') == 'True'

    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')
    mail.init_app(app)

    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, "elf.db")
    db_url = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")
    app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_db_url(db_url)

    db.init_app(app)
    migrate.init_app(app, db)

    if os.getenv("USE_PROXY_FIX", "true").lower() in ("1", "true", "yes"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    configure_logging(app)
    from routes import main_bp
    app.register_blueprint(main_bp)

    @app.cli.command("init-db")
    def init_db_command():
        seed = os.getenv("SEED_DB", "false").lower() in ("1", "true", "yes")
        with app.app_context():
            setup_database(seed=seed)
        print("Database initialized.")

    return app


app = create_app()


if __name__ == "__main__":
    auto_init = os.getenv("AUTO_INIT_DB", "false").lower() in ("1", "true", "yes")
    if auto_init:
        seed = os.getenv("SEED_DB", "false").lower() in ("1", "true", "yes")
        with app.app_context():
            setup_database(seed=seed)
