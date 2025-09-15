# set_alembic_version.py

import os
from app import app, db # 'app' 객체와 'db' 객체를 가져오는 경로를 정확히 확인하세요.
from sqlalchemy.exc import IntegrityError
from datetime import datetime

# Render 환경 변수에서 DATABASE_URL을 사용하도록 설정
# if os.environ.get("DATABASE_URL"):
#     app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
# else:
#     # 로컬 개발 환경용 기본값 (필요시 수정)
#     app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///your_local_database.db"

# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask 앱 컨텍스트 내에서 데이터베이스 작업 수행
with app.app_context():
    try:
        # alembic_version 테이블이 없으면 생성
        # Alembic이 사용하는 테이블 구조와 일치해야 합니다.
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            );
        """))
        db.session.commit() # CREATE TABLE 실행 후 커밋

        # 특정 버전 번호를 alembic_version 테이블에 삽입
        # 오류를 일으키는 마이그레이션 버전 ID를 여기에 넣으세요.
        version_to_set = '189e0722533a' # 에러 메시지에 나온 해당 버전 ID

        # 이미 존재하는지 확인 후 삽입 (중복 에러 방지)
        existing_version = db.session.execute(
            db.text("SELECT version_num FROM alembic_version WHERE version_num = :version"),
            {'version': version_to_set}
        ).scalar_one_or_none()

        if not existing_version:
            db.session.execute(
                db.text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
                {'version': version_to_set}
            )
            db.session.commit()
            print(f"Alembic version '{version_to_set}' set successfully.")
        else:
            print(f"Alembic version '{version_to_set}' already exists. Skipping insertion.")

    except IntegrityError:
        db.session.rollback()
        print(f"Alembic version '{version_to_set}' already exists (IntegrityError). Skipping insertion.")
    except Exception as e:
        db.session.rollback()
        print(f"Error setting Alembic version: {e}")

print("Alembic version setup script finished.")