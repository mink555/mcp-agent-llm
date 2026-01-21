# BFCL 벤치마크 사용 가이드

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# API 키 설정 (.env 파일 생성)
echo "OPENROUTER_API_KEY=your-api-key-here" > .env
```

### 2. 빠른 샘플 테스트 (권장)

```bash
# 2개 카테고리 x 2개 샘플 = 총 4개 테스트
python main.py --quick
```

**예상 소요 시간:** 약 10초  
**결과 파일:** `results/BFCL_QUICK_Report_YYYYMMDD_HHMMSS.xlsx`

### 3. 전체 벤치마크 실행

```bash
# 20개 카테고리 x 5개 샘플 = 총 100개 테스트
python main.py

# 전체 데이터셋 (약 4,693개)
python main.py --full
```

**예상 소요 시간:** 약 15-20분 (기본), 3-4시간 (전체)
**결과 파일:** `results/BFCL_FULL_Report_YYYYMMDD_HHMMSS.xlsx`

---

## 📋 커스텀 실행 옵션

### 샘플 수 조정

```bash
# 각 카테고리당 3개씩 테스트
python main.py --samples 3
```

### 특정 카테고리만 테스트

```bash
# simple_python과 multiple만 테스트
python main.py --categories simple_python multiple --samples 2
```

### 다른 모델 사용

```bash
# GPT-4 사용 (OpenRouter 통해)
python main.py --quick --model "openai/gpt-4o-mini"

# Claude 사용
python main.py --quick --model "anthropic/claude-3-haiku"

# 다른 Mistral 버전
python main.py --quick --model "mistralai/mistral-large"
```

### 대기 시간 조정

API 레이트 리밋을 고려하여 카테고리 간 대기 시간을 조정할 수 있습니다.

```bash
# 대기 시간을 1초로 줄여서 빠르게 실행
python main.py --quick --delay 1

# 대기 시간 없이 실행 (레이트 리밋이 없는 경우)
python main.py --delay 0

# 대기 시간을 10초로 늘려서 안전하게 실행
python main.py --full --delay 10
```

**기본값:**
- `--quick`: 5초
- `--full`: 3초
- 기본 모드: 3초

### 조합 예시

```bash
# 3개 카테고리, 각 3개 샘플, GPT-4로 실행
python main.py \
  --categories simple_python multiple parallel \
  --samples 3 \
  --model "openai/gpt-4o-mini"
```

---

## 📂 테스트 카테고리 (전체 20개)

### AST Non-Live (6개)
| 카테고리 | 설명 | 난이도 |
|---------|------|--------|
| `simple_python` | 단일 Python 함수 호출 | ⭐ |
| `simple_javascript` | 단일 JavaScript 함수 호출 | ⭐ |
| `simple_java` | 단일 Java 함수 호출 | ⭐ |
| `multiple` | 여러 파라미터를 가진 함수 호출 | ⭐⭐ |
| `parallel` | 병렬 함수 호출 | ⭐⭐ |
| `parallel_multiple` | 복잡한 병렬 호출 | ⭐⭐⭐ |

### AST Live (4개)
| 카테고리 | 설명 | 난이도 |
|---------|------|--------|
| `live_simple` | 실시간 API 단일 호출 | ⭐⭐ |
| `live_multiple` | 실시간 API 다중 파라미터 | ⭐⭐ |
| `live_parallel` | 실시간 API 병렬 호출 | ⭐⭐⭐ |
| `live_parallel_multiple` | 실시간 API 복잡한 병렬 | ⭐⭐⭐ |

### Multi-Turn (4개)
| 카테고리 | 설명 | 난이도 |
|---------|------|--------|
| `multi_turn_base` | 멀티턴 대화 | ⭐⭐⭐ |
| `multi_turn_miss_func` | 함수 누락 처리 | ⭐⭐⭐ |
| `multi_turn_miss_param` | 파라미터 누락 처리 | ⭐⭐⭐ |
| `multi_turn_long_context` | 긴 컨텍스트 처리 | ⭐⭐⭐⭐ |

### Relevance Detection (3개)
| 카테고리 | 설명 | 난이도 |
|---------|------|--------|
| `irrelevance` | 관련 없는 질문 처리 | ⭐⭐ |
| `live_irrelevance` | 실시간 API 관련없음 회피 | ⭐⭐ |
| `live_relevance` | 실시간 API 관련 함수 탐지 | ⭐⭐ |

### Agentic (3개)
| 카테고리 | 설명 | 난이도 |
|---------|------|--------|
| `web_search` | 웹 검색 에이전트 | ⭐⭐⭐ |
| `memory` | 메모리 관리 | ⭐⭐⭐ |
| `format_sensitivity` | 포맷 민감도 | ⭐⭐ |

---

## 📊 결과 파일 형식

생성된 Excel 파일은 **4개의 시트**로 구성됩니다:

### 1️⃣ Detailed Results (상세 결과)

| 컬럼 | 설명 |
|-----|------|
| **카테고리** | 테스트 카테고리 |
| **ID** | 테스트 케이스 ID |
| **결과** | PASS / FAIL |
| **질문** | 사용자 질문 |
| **검증 상세** | 상세 검증 결과 |
| **사고과정** | 모델의 추론 과정 (if available) |
| **누적 호출(AST)** | 모델이 호출한 함수 목록 (JSON) |
| **정답(GT)** | 정답 함수 호출 (Ground Truth) |
| **Latency** | 응답 시간 (ms) |

### 2️⃣ Summary (BFCL) (요약 통계)

BFCL 공식 점수 산출 방법에 따른 통계:
- **Overall Accuracy**: 전체 카테고리의 unweighted average (BFCL 표준)
- **Group Scores**: AST_NON_LIVE, AST_LIVE, MULTI_TURN 그룹별 평균
- **Category Scores**: 각 카테고리별 정확도 (PASS/Total)

### 3️⃣ Dataset Info (데이터셋 정보)

전체 20개 BFCL 카테고리 정보:
- 카테고리명, 전체 데이터 개수, 그룹, 난이도, 설명

### 4️⃣ Reference (참고 자료)

BFCL 공식 문서, 평가 방법, 논문 링크 등

---

## 🎯 성공 예시

```bash
$ python main.py --quick

================================================================================
🚀 BFCL 벤치마크 시작
================================================================================
📋 모델: mistralai/mistral-small-3.2-24b-instruct
📂 카테고리: simple_python, multiple
📊 카테고리당 샘플: 2개
🎯 총 예상 테스트: 4개
================================================================================

[1/2] 📂 Category: simple_python
  [1/2] Testing: simple_python_0... ✅ (1019ms)
  [2/2] Testing: simple_python_1... ✅ (678ms)

[2/2] 📂 Category: multiple
  [1/2] Testing: multiple_0... ✅ (1524ms)
  [2/2] Testing: multiple_1... ✅ (753ms)

================================================================================
✅ 벤치마크 완료!
================================================================================
📊 총 테스트: 4개
✅ PASS: 4개 (100.0%)
❌ FAIL: 0개
⏱️  소요 시간: 9.0초
💾 저장 위치: results/BFCL_QUICK_Report_20260121_100724.xlsx
================================================================================
```

---

## 🔧 트러블슈팅

### API 키 에러

```
ValueError: OPENROUTER_API_KEY가 설정되지 않았습니다.
```

**해결:** `.env` 파일에 API 키를 설정하세요.

```bash
echo "OPENROUTER_API_KEY=sk-or-v1-..." > .env
```

### 404 모델 에러

```
Error code: 404 - {'error': {'message': 'model not found'}}
```

**해결:** 올바른 모델 이름을 사용하세요. OpenRouter 문서에서 확인: https://openrouter.ai/docs

### 도구 호출 실패 (0% PASS)

**원인:** Free 모델은 tool calling 지원이 제한적일 수 있습니다.

**해결:** 유료 모델을 사용하세요.

```bash
python main.py --quick --model "mistralai/mistral-small-3.2-24b-instruct"
```

---

## 📈 프롬프트 엔지니어링

### 현재 적용된 Best Practices

1. **명확한 역할 정의**: "expert function-calling assistant"
2. **Critical Rules 강조**: ALWAYS use functions, NEVER hallucinate
3. **파라미터 추출 가이드**: 사용자 질문에서 직접 추출
4. **멀티턴 전략**: 도구 결과를 다음 호출에 활용

### 커스터마이징

프롬프트를 수정하려면 `main.py`의 `SYSTEM_PROMPT` 변수를 편집하세요 (84-108번 줄).

---

## 🆘 도움말

```bash
python main.py --help
```

---

## 📝 라이센스

MIT License
