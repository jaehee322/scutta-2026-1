import os
import signal
import sys
from urllib.parse import urlparse
from flask import Flask
from config import Config
from .extensions import db, migrate, login_manager
from .models import User

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # ▼▼▼▼▼ 최종 수정 파트 1: DB 주소 직접 설정 ▼▼▼▼▼
    # Render 환경 변수에서 DATABASE_URL을 직접 가져옵니다.
    db_url = os.environ.get('DATABASE_URL')

    # Render의 postgres:// 주소를 SQLAlchemy가 인식하는 postgresql://로 변경합니다.
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    # 앱 설정에 최종적으로 수정된 DB 주소를 강제로 할당합니다.
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    # ▲▲▲▲▲ 여기까지 수정 ▲▲▲▲▲

    # SSL 설정 등 기존 로직은 그대로 유지합니다.
    parsed_url = urlparse(db_url or "")
    if parsed_url.hostname and "render.com" in parsed_url.hostname:
        sslmode = "require"
    else:
        sslmode = "disable"
    
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'sslmode': sslmode}
    }
    
    db.init_app(app)
    migrate.init_app(app, db) # Flask-Migrate 초기화
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        from . import routes
        routes.init_routes(app)

    return app