import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

class Config:
   
    db_url = os.getenv("DATABASE_URL")
    
    # db_url이 정상적으로 로드되지 않았을 경우를 대비한 예외 처리
    if db_url is None:
        raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")

    parsed_url = urlparse(db_url)
   
    if parsed_url.hostname and "singapore-postgres.render.com" in parsed_url.hostname:
        if "sslmode" not in db_url:
            db_url += "?sslmode=require"
    else:
        if "sslmode" not in db_url:
            db_url += "?sslmode=disable"

    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY') or 'a-default-secret-key'