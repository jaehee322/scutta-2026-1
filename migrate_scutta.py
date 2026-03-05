"""스쿠타 포인트 DB 마이그레이션 — 직접 SQL 실행"""
import os
from dotenv import load_dotenv
load_dotenv()

import sqlalchemy as sa

# DB URL 가져오기
db_url = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
if not db_url:
    # config.py에서 가져오기
    from config import Config
    db_url = Config.SQLALCHEMY_DATABASE_URI

print(f"DB URL: {db_url[:30]}...")

engine = sa.create_engine(db_url)

with engine.connect() as conn:
    # 1. player 테이블에 scutta_count 컬럼 추가 (없으면)
    try:
        conn.execute(sa.text("ALTER TABLE player ADD COLUMN scutta_count INTEGER DEFAULT 0"))
        conn.commit()
        print("✅ player.scutta_count 컬럼 추가 완료")
    except Exception as e:
        conn.rollback()
        if 'already exists' in str(e) or 'duplicate' in str(e).lower():
            print("⏭️ player.scutta_count 이미 존재")
        else:
            print(f"❌ player.scutta_count 오류: {e}")

    # 2. player 테이블에 scutta_order 컬럼 추가 (없으면)
    try:
        conn.execute(sa.text("ALTER TABLE player ADD COLUMN scutta_order INTEGER DEFAULT NULL"))
        conn.commit()
        print("✅ player.scutta_order 컬럼 추가 완료")
    except Exception as e:
        conn.rollback()
        if 'already exists' in str(e) or 'duplicate' in str(e).lower():
            print("⏭️ player.scutta_order 이미 존재")
        else:
            print(f"❌ player.scutta_order 오류: {e}")

    # 3. player_point_log 테이블에 scutta_change 컬럼 추가 (없으면)
    try:
        conn.execute(sa.text("ALTER TABLE player_point_log ADD COLUMN scutta_change INTEGER DEFAULT 0"))
        conn.commit()
        print("✅ player_point_log.scutta_change 컬럼 추가 완료")
    except Exception as e:
        conn.rollback()
        if 'already exists' in str(e) or 'duplicate' in str(e).lower():
            print("⏭️ player_point_log.scutta_change 이미 존재")
        else:
            print(f"❌ player_point_log.scutta_change 오류: {e}")

    # 4. 기존 데이터 초기화
    try:
        conn.execute(sa.text("UPDATE player SET scutta_count = 0 WHERE scutta_count IS NULL"))
        conn.execute(sa.text("UPDATE player_point_log SET scutta_change = 0 WHERE scutta_change IS NULL"))
        conn.commit()
        print("✅ 기존 데이터 초기값(0) 설정 완료")
    except Exception as e:
        conn.rollback()
        print(f"⚠️ 초기값 설정: {e}")

    # 5. 확인
    result = conn.execute(sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='player' AND column_name IN ('scutta_count','scutta_order')"))
    cols = [row[0] for row in result]
    print(f"\n🔍 player 테이블 scutta 컬럼: {cols}")

    result = conn.execute(sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='player_point_log' AND column_name='scutta_change'"))
    cols = [row[0] for row in result]
    print(f"🔍 player_point_log 테이블 scutta 컬럼: {cols}")

print("\n🎉 마이그레이션 완료!")
