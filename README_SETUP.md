# 설정 가이드 (Setup Guide)

## 1. 환경 변수 설정

프로젝트를 실행하기 전에 API 키를 설정해야 합니다.

### 단계별 설정:

1. `.env.example` 파일을 복사하여 `.env` 파일을 생성합니다:
   ```bash
   cp .env.example .env
   ```

2. `.env` 파일을 열고 실제 API 키를 입력합니다:
   ```bash
   OPENROUTER_API_KEY=your_actual_api_key_here
   ```

3. OpenRouter API 키 발급 방법:
   - [OpenRouter 웹사이트](https://openrouter.ai/keys)에 접속
   - 계정 생성 또는 로그인
   - API Keys 메뉴에서 새 키 생성
   - 생성된 키를 `.env` 파일에 입력

## 2. 의존성 설치

```bash
pip install -r requirements.txt
```

## 3. 실행

```bash
# 빠른 테스트
python main.py --quick

# 전체 벤치마크
python main.py --full
```

## ⚠️ 보안 주의사항

- ✅ `.env` 파일은 절대 Git에 커밋하지 마세요
- ✅ `.env` 파일은 이미 `.gitignore`에 포함되어 있습니다
- ✅ API 키는 절대 공개하지 마세요
- ✅ `.env.example`에는 실제 키를 넣지 말고 예시만 작성하세요
