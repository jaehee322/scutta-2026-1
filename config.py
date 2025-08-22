import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 1. Render 환경 변수에서 데이터베이스 주소를 가져옵니다.
    db_url = os.environ.get('DATABASE_URL')

    # 2. Render의 'postgres://' 주소를 SQLAlchemy가 알아듣는 'postgresql://'로 바꿔줍니다.
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # 3. 최종 DB 주소와 SECRET_KEY를 설정합니다.
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a-very-secret-key')

    # 4. SSL 연결 설정을 위한 옵션을 추가합니다. (Render DB는 SSL 연결이 필요합니다.)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'sslmode': 'require'
        }
    }