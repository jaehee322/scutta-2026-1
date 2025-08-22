import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Render의 환경 변수에서 데이터베이스 주소를 가져옵니다.
    db_url = os.getenv("DATABASE_URL")
    
    if db_url is None:
        raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")

    # ▼▼▼▼▼ 바로 이 한 줄이 모든 문제를 해결합니다! ▼▼▼▼▼
    # Render가 주는 'postgres://' 주소를 SQLAlchemy가 알아듣는 'postgresql://'로 바꿔줍니다.
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    # ▲▲▲▲▲ 이 부분이 추가되었습니다 ▲▲▲▲▲

    # 이하는 기존의 좋은 로직을 그대로 사용합니다.
    parsed_url = urlparse(db_url)
   
    if parsed_url.hostname and "render.com" in parsed_url.hostname:
        if "sslmode" not in db_url:
            db_url += "?sslmode=require"
    else:
        if "sslmode" not in db_url:
            db_url += "?sslmode=disable"

    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY') or 'a-default-secret-key'