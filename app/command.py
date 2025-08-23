import click
from flask.cli import with_appcontext
from .models import User, Player, GenderEnum, FreshmanEnum
from .extensions import db

def register_commands(app):
    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("password")
    @with_appcontext
    def create_admin(username, password):
        """새로운 관리자 계정을 생성합니다."""
        if User.query.filter_by(username=username).first():
            print(f">>> 오류: '{username}' 사용자는 이미 존재합니다.")
            return

        # 관리자 계정과 연결된 Player 객체 생성
        admin_player = Player(
            name=username,
            gender=GenderEnum.MALE, 
            is_she_or_he_freshman=FreshmanEnum.No,
            rank=0
        )
        db.session.add(admin_player)
        
        # is_admin=True로 설정하여 User 객체 생성
        admin_user = User(
            username=username,
            is_admin=True,
            player=admin_player
        )
        admin_user.set_password(password)
        db.session.add(admin_user)
        
        db.session.commit()
        print(f">>> 성공: 관리자 '{username}' 계정이 생성되었습니다.")