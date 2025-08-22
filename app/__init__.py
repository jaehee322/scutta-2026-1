import os
import signal
import sys
from urllib.parse import urlparse
from flask import Flask
from config import Config
from .extensions import db, migrate, login_manager
from .models import User # User 모델을 여기서 import합니다.

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    app.config['GLOBAL_TEXTS'] = {
        'semester': '2025-2'
    }
    
    # ▼▼▼▼▼ 핵심 수정 부분 ▼▼▼▼▼
    # Render의 postgres:// 주소를 SQLAlchemy가 인식하는 postgresql://로 변경합니다.
    db_url = app.config.get("SQLALCHEMY_DATABASE_URI")
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    # ▲▲▲▲▲ 여기까지가 수정된 부분입니다 ▲▲▲▲▲

    # 이하는 보내주신 코드의 좋은 로직을 그대로 유지합니다.
    parsed_url = urlparse(db_url or "")
    if parsed_url.hostname and "render.com" in parsed_url.hostname:
        sslmode = "require"
    else:
        sslmode = "disable"
    
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'sslmode': sslmode}
    }
    
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_config():
        return dict(config=app.config)

    # routes 초기화
    from . import routes
    routes.init_routes(app)

    # Graceful shutdown 시그널 핸들러
    def handle_exit_signal(signum, frame):
        print("Shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, handle_exit_signal)
    signal.signal(signal.SIGINT, handle_exit_signal)

    return app