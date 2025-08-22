from flask import Flask
from config import Config
from .extensions import db, migrate, login_manager
from .models import User

def create_app():
    app = Flask(__name__)
    # config.py의 Config 클래스에서 모든 설정을 불러옵니다.
    app.config.from_object(Config)
    
    # 전역 변수 설정
    app.config['GLOBAL_TEXTS'] = {
        'semester': '2025-2'
    }
    
    # 확장 초기화
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # routes 초기화
    from . import routes
    routes.init_routes(app)

    return app