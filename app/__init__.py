from flask import Flask, session, redirect, url_for, request, g, current_app
from . import commands
from config import Config
from .extensions import db, migrate, login_manager, babel
from .models import User
from flask_babel import _, lazy_gettext as _l
from flask import Flask
from datetime import datetime
from zoneinfo import ZoneInfo

def get_locale():
    if 'lang' in session:
        return session['lang']
    return request.accept_languages.best_match(
        current_app.config['BABEL_SUPPORTED_LOCALES']
    )

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.config['GLOBAL_TEXTS'] = {'semester': '2026-1'}
    app.config['BABEL_DEFAULT_LOCALE'] = 'ko'
    app.config['BABEL_SUPPORTED_LOCALES'] = ['ko', 'en']
    # 필요시 번역 디렉터리 지정(기본값은 'translations')
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
    app.config['SEASON_START'] = datetime(2025, 9, 1, 0, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    app.config['SEMESTER_DEADLINE'] = datetime(2025, 12, 13, 0, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    # 여기서 get_locale을 넘겨줍니다.
    babel.init_app(app, locale_selector=get_locale)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from . import routes
    routes.init_routes(app)
    commands.register_commands(app)

    @app.route('/set_language/<lang_code>')
    def set_language(lang_code):
        if lang_code in app.config['BABEL_SUPPORTED_LOCALES']:
            session['lang'] = lang_code
        return redirect(request.referrer or url_for('index'))

    return app
