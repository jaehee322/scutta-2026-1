#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing requirements..."
pip install -r requirements.txt


# 새로운 마이그레이션(변경사항)들을 적용
flask db upgrade

echo "Build and Migration completed successfully!"
