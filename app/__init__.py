import signal
import sys
from urllib.parse import urlparse
from flask import Flask
from config import Config
from .extensions import db, migrate, login_manager

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
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @app.context_processor
    def inject_config():
        return dict(config=app.config)

    with app.app_context():
        from . import models
        from . import routes

        routes.init_routes(app)

        @login_manager.user_loader
        def load_user(user_id):
            return models.User.query.get(int(user_id))

    def handle_exit_signal(signum, frame):
        print("Shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, handle_exit_signal)
    signal.signal(signal.SIGINT, handle_exit_signal)

    return app