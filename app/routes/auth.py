from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
from flask_babel import _
from ..extensions import db
from ..models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = True if request.form.get('remember') else False
        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash(_('아이디 또는 비밀번호가 올바르지 않습니다.'))
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember_me)
        return redirect(url_for('main.index'))

    return render_template('login.html', global_texts=current_app.config['GLOBAL_TEXTS'])


@auth_bp.route('/logout')
def logout():
    session.pop('_flashes', None)
    logout_user()
    return redirect(url_for('main.index'))


@auth_bp.route('/set_language/<lang_code>')
def set_language(lang_code):
    if lang_code in current_app.config['BABEL_SUPPORTED_LOCALES']:
        session['lang'] = lang_code
    return redirect(request.referrer or url_for('main.index'))


@auth_bp.route('/password')
@login_required
def password():
    return render_template('password.html', global_texts=current_app.config['GLOBAL_TEXTS'])


@auth_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    user_to_update = User.query.get(current_user.id)
    if not user_to_update:
        flash(_('사용자 정보를 찾을 수 없습니다.'), 'error')
        return redirect(url_for('auth.change_password_page'))

    if not user_to_update.check_password(current_password):
        flash(_('현재 비밀번호가 일치하지 않습니다.'), 'error')
        return redirect(url_for('auth.change_password_page'))

    if new_password != confirm_password:
        flash(_('새로운 비밀번호가 일치하지 않습니다.'), 'error')
        return redirect(url_for('auth.change_password_page'))

    if len(new_password) < 4:
        flash(_('새로운 비밀번호는 4자 이상이어야 합니다.'), 'error')
        return redirect(url_for('auth.change_password_page'))

    user_to_update.set_password(new_password)
    db.session.commit()

    flash(_('비밀번호가 성공적으로 변경되었습니다.'), 'success')
    return redirect(url_for('main.mypage'))


@auth_bp.route('/change_password_page')
@login_required
def change_password_page():
    return render_template('change_password.html')
