import signal
import sys
from urllib.parse import urlparse
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()

migrate = Migrate()

def handle_exit_signal(signum, frame):
    print("Shutting down gracefully...")
    sys.exit(0)

def create_app():
        
    app = Flask(__name__)
    app.config.from_object(Config)
    
    app.config['GLOBAL_TEXTS'] = {
        'semester': '2025-2'
    }
    
    db_url = app.config["SQLALCHEMY_DATABASE_URI"]
    parsed_url = urlparse(db_url)
    
    if parsed_url.hostname and "singapore-postgres.render.com" in parsed_url.hostname:
        sslmode = "require"
    else:
        sslmode = "disable"
    
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_size': 5,
        'max_overflow': 10,
        'connect_args': {'sslmode': sslmode}
    }
    
    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        from . import routes, models
        try:
            db.create_all()
        except Exception as e:
            app.logger.error(f"Database initialization error: {e}")
            raise
    
    signal.signal(signal.SIGTERM, handle_exit_signal)
    signal.signal(signal.SIGINT, handle_exit_signal)

    return app
