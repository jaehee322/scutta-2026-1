"""DB 마이그레이션 스크립트 — 리그전 4~6인 확장용 컬럼 추가"""
import os
from dotenv import load_dotenv
load_dotenv()

import sqlalchemy as sa

# DB URL 가져오기
db_url = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
if db_url and db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

engine = sa.create_engine(db_url)

with engine.connect() as conn:
    # p5를 nullable로 변경 (이미 nullable이면 무시)
    try:
        conn.execute(sa.text("ALTER TABLE league ALTER COLUMN p5 DROP NOT NULL"))
        conn.commit()
        print("[OK] p5 nullable로 변경 완료")
    except Exception as e:
        conn.rollback()
        print(f"[SKIP] p5 nullable 변경: {e}")

    # 새 컬럼 추가 (이미 있으면 무시)
    new_columns = [
        ("league", "p6", "VARCHAR(100)"),
        ("league", "p1p6", "INTEGER"),
        ("league", "p2p6", "INTEGER"),
        ("league", "p3p6", "INTEGER"),
        ("league", "p4p6", "INTEGER"),
        ("league", "p5p6", "INTEGER"),
        ("league", "p6p1", "INTEGER"),
        ("league", "p6p2", "INTEGER"),
        ("league", "p6p3", "INTEGER"),
        ("league", "p6p4", "INTEGER"),
        ("league", "p6p5", "INTEGER"),
    ]

    for table, col, col_type in new_columns:
        try:
            conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
            conn.commit()
            print(f"[OK] {table}.{col} 컬럼 추가 완료")
        except Exception as e:
            conn.rollback()
            print(f"[SKIP] {table}.{col}: {e}")

    print("\n=== 마이그레이션 완료! ===")
