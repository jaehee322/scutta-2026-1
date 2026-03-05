#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing requirements..."
pip install -r requirements.txt

echo "Fixing Alembic Migration Sync Issue..."
# Render DB에 Alembic 버전이 없을 경우를 대비한 stamp (이미 찍혀있다면 무시됨)
# 현재 Render DB에 적용 완료된 최신 리비전으로 도장
flask db stamp 0e6a82b8f6f3 || true

# 새로운 마이그레이션(변경사항)들을 적용
flask db upgrade

echo "Build and Migration completed successfully!"
