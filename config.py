import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    

    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a-very-secret-key')

    # 현재 환경이 Render인지 확인 
    is_render_env = 'IS_PULL_REQUEST' in os.environ

    # Render 환경일 경우에만 SSL 연결을 요구하도록 수정
    if is_render_env:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'connect_args': {
                'sslmode': 'require'
            }
        }
    # 로컬 환경에서는 SSL 설정을 적용하지 않음
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {}
  