import os
from dotenv import load_dotenv

print("--- 테스트 시작 ---")

# .env 파일을 로드합니다.
load_dotenv()
print(".env 파일을 로드했습니다.")

# DATABASE_URL 환경 변수를 읽어옵니다.
db_url = os.environ.get('DATABASE_URL')

print(f"읽어온 DATABASE_URL: {db_url}")

if db_url:
    print("\n[성공] .env 파일에서 DATABASE_URL을 성공적으로 읽었습니다!")
else:
    print("\n[실패] .env 파일을 읽었지만 DATABASE_URL을 찾지 못했거나, 파일 자체를 읽지 못했습니다.")
    
print("--- 테스트 종료 ---")
