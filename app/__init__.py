from flask import Flask
from config import Config
from .extensions import db, migrate, login_manager
from .models import User

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    app.config['GLOBAL_TEXTS'] = {
        'semester': '2025-2'
    }
    
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ▼▼▼▼▼ 이 부분이 수정되었습니다 ▼▼▼▼▼
    # routes와 함께 commands를 import하고, 앱에 명령어를 등록합니다.
    from . import routes, commands
    routes.init_routes(app)
    commands.register_commands(app)
    # ▲▲▲▲▲ 여기까지 입니다 ▲▲▲▲▲

    return app