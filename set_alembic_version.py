# set_alembic_version.py

import os
from app import create_app
from app.extensions import db
from sqlalchemy.exc import IntegrityError
from datetime import datetime

# 2. app 팩토리 함수를 호출하여 app 객체를 생성합니다.
#    config_class를 지정해야 한다면 create_app(Config)와 같이 호출합니다.
app = create_app()

# 3. 이제 생성된 app 객체의 컨텍스트 안에서 작업을 수행합니다.
with app.app_context():
    try:
        # alembic_version 테이블이 없으면 생성
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            );
        """))
        db.session.commit()

        # 특정 버전 번호를 alembic_version 테이블에 삽입
        version_to_set = '189e0722533a'

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