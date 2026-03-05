#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing requirements..."
pip install -r requirements.txt

echo "Fixing Alembic Migration Sync Issue..."
# Render DB에는 테이블이 이미 있지만 Alembic 버전(stamp)이 없어서 생기는 Duplicate 에러 방지용.
# 1. 초기 생성 마이그레이션 도장 (이미 찍혀있다면 무시됨)
flask db stamp 00bd16465ddb || true

# 2. 새로운 마이그레이션(변경사항)들을 적용
flask db upgrade

echo "Build and Migration completed successfully!"
