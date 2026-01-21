# MCP LLM Benchmark

Berkeley Function Calling Leaderboard (BFCL) 벤치마크를 쉽게 실행할 수 있는 도구입니다.

## 📊 데이터셋 통계

전체 **4,693개**의 테스트 샘플이 20개 카테고리에 분포되어 있습니다.

### 카테고리별 샘플 개수

| 카테고리 | 샘플 수 | 그룹 | 난이도 |
|---------|--------|------|-------|
| **simple_python** | 399 | AST Non-Live | ⭐ |
| **simple_javascript** | 49 | AST Non-Live | ⭐ |
| **simple_java** | 99 | AST Non-Live | ⭐ |
| **multiple** | 199 | AST Non-Live | ⭐⭐ |
| **parallel** | 199 | AST Non-Live | ⭐⭐ |
| **parallel_multiple** | 199 | AST Non-Live | ⭐⭐⭐ |
| **live_simple** | 257 | AST Live | ⭐⭐ |
| **live_multiple** | 1,052 | AST Live | ⭐⭐ |
| **live_parallel** | 15 | AST Live | ⭐⭐⭐ |
| **live_parallel_multiple** | 23 | AST Live | ⭐⭐⭐ |
| **multi_turn_base** | 200 | Multi-turn | ⭐⭐⭐ |
| **multi_turn_miss_func** | 200 | Multi-turn | ⭐⭐⭐ |
| **multi_turn_miss_param** | 200 | Multi-turn | ⭐⭐⭐ |
| **multi_turn_long_context** | 200 | Multi-turn | ⭐⭐⭐⭐ |
| **irrelevance** | 239 | Relevance | ⭐⭐ |
| **live_irrelevance** | 884 | Relevance | ⭐⭐ |
| **live_relevance** | 16 | Relevance | ⭐⭐ |
| **web_search** | 99 | Agentic | ⭐⭐⭐ |
| **memory** | 155 | Agentic | ⭐⭐⭐ |
| **format_sensitivity** | 9 | Agentic | ⭐⭐ |

---

## 🎯 BFCL 공식 평가 방법 준수

본 구현은 BFCL 공식 평가 방법론을 완벽하게 준수합니다:

### 1. Single-Turn: AST Exact Match ✅
- **방법**: 호출 개수와 파라미터 구조가 정확히 일치해야 PASS
- **Parallel**: 순서 무관 (order-independent matching)
- **적용**: `simple_*`, `multiple`, `parallel`, `live_*` 카테고리

### 2. Multi-Turn: Response-Based (Subset Matching) ✅

**공식 BFCL V3 규칙**: Ground Truth must be a **strict subset** of model result

#### 평가 규칙 (출처: [BFCL V3 Blog](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html))

| 규칙 | 설명 | 예시 |
|------|------|------|
| **Subset Matching** | GT의 모든 함수 호출이 모델 출력에 포함되어야 함 | GT: `[A, B, C]` → Model: `[A, B, C, D]` ✅ |
| **Order Independent** | 순서는 무관 | GT: `[A, B, C]` → Model: `[C, B, A]` ✅ |
| **Duplicates Allowed** | 중복 호출 허용 (탐색 과정에서 자연스럽게 발생) | GT: `[A, B]` → Model: `[A, ls, B, ls]` ✅ |
| **All-or-Nothing** | 하나라도 누락되면 FAIL | GT: `[A, B, C]` → Model: `[A, B]` ❌ (C 누락) |
| **State + Response** | Multi-turn은 state-based & response-based 모두 통과 필요 | 두 체커 모두 PASS해야 최종 PASS |

#### Minimal Viable Execution Paths

Ground Truth는 사용자 요청에 응답하기 위해 **반드시 실행되어야 하는** 함수 호출 목록입니다.

**예시 1: 파일 이동 작업**
```python
# User: "Move report.pdf to archive folder"
GT:  ["cd('documents')", "mkdir('archive')", "mv('report.pdf', 'archive')"]

# Model의 탐색 과정 (중복 허용)
Model: ["ls()", "cd('documents')", "ls()", "mkdir('archive')", "mv('report.pdf', 'archive')", "ls()"]
Result: ✅ PASS (모든 GT 포함, 중복 3개 허용)
```

**예시 2: 일부 누락 (FAIL)**
```python
GT:  ["cd('workspace')", "grep('log.txt', 'Error')", "tail('log.txt', 20)"]
Model: ["cd('workspace')", "grep('log.txt', 'Error')"]  # tail 누락
Result: ❌ FAIL (3/3 중 2개만 매칭, 67%)
```

- **적용**: `multi_turn_*` 카테고리

### 3. Relevance: Detection ✅
- **Irrelevance**: 함수 호출 없음 = PASS
- **Relevance**: 최소 1개 호출 = PASS (정확도 체크 안 함)
- **적용**: `irrelevance`, `live_irrelevance`, `live_relevance`

### 4. Agentic: Exact Match ✅
- **방법**: 최종 답변에 정답 문자열 포함 여부
- **적용**: `web_search`, `memory`

> 📖 상세 구현 문서: [BFCL_IMPLEMENTATION.md](./BFCL_IMPLEMENTATION.md)

---

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone https://github.com/mink555/mcp-agent-llm.git
cd mcp-agent-llm

# 의존성 설치
pip install -r requirements.txt

# API 키 설정
cp .env.example .env
# .env 파일을 열고 OPENROUTER_API_KEY를 입력하세요
```

### 2. 벤치마크 실행

#### 옵션 비교

| 옵션 | 테스트 수 | 예상 시간 | 용도 |
|------|----------|----------|------|
| `--quick` | **6개** (3개 카테고리 × 2개) | ~2분 | 빠른 테스트 |
| 기본 | **100개** (20개 카테고리 × 5개) | ~15분 | 일반 평가 |
| `--full` | **~4,693개** (전체) | ~3-4시간 | 완전한 벤치마크 |
| `--samples N` | **20 × N개** | 가변 | 커스텀 |

#### 실행 예시

```bash
# 빠른 테스트 (권장 - 처음 시도)
python main.py --quick

# 기본 벤치마크 (각 카테고리 5개)
python main.py

# 전체 벤치마크 (모든 데이터)
python main.py --full

# 커스텀 샘플 수
python main.py --samples 10

# 특정 카테고리만 테스트
python main.py --categories simple_python multiple --samples 3

# 다른 모델 사용
python main.py --model "anthropic/claude-3-haiku" --quick

# 대기 시간을 줄여서 빠르게 실행
python main.py --quick --delay 1

# 다중 모델 순차 실행 (20개 카테고리 × 10개 샘플 × 5개 모델 = 1,000개 테스트)
python run_multi_models.py
```

## 📈 결과 확인

벤치마크 실행 후 `results/` 폴더에 Excel 리포트가 생성됩니다.

### 리포트 구성 (4개 시트)

1. **Detailed Results**: 각 테스트의 상세 결과
2. **Summary (BFCL)**: 카테고리별/그룹별 통계 (Excel 수식으로 자동 계산)
3. **Dataset Info**: 데이터셋 정보 및 카테고리 설명
4. **Reference**: BFCL 공식 참고 자료

### 점수 산출 방식

```
Overall Accuracy = Σ(Category Accuracy) / N
```

- 모든 카테고리에 동일한 가중치 부여 (BFCL 표준)
- 카테고리별 정확도 = (PASS 개수 / 전체 개수) × 100%

## 🎯 지원 모델

OpenRouter를 통해 다음 모델들을 지원합니다:

- Mistral (mistralai/mistral-small-3.2-24b-instruct) - 기본값
- Claude (anthropic/claude-3-haiku, claude-3-sonnet 등)
- GPT (openai/gpt-4o-mini, gpt-4o 등)
- Llama (meta-llama/llama-3.3-70b-instruct 등)
- Qwen (qwen/qwen3-next-80b-a3b 등)

전체 모델 목록: https://openrouter.ai/models

## 📝 추가 문서

- [USAGE.md](USAGE.md): 상세 사용법
- [BFCL_IMPLEMENTATION.md](BFCL_IMPLEMENTATION.md): 구현 상세
- [README_SETUP.md](README_SETUP.md): 환경 설정 가이드

## 🔗 참고 자료

- [BFCL 공식 사이트](https://gorilla.cs.berkeley.edu/leaderboard.html)
- [BFCL GitHub](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard)
- [BFCL 데이터셋](https://huggingface.co/datasets/gorilla-llm/Berkeley-Function-Calling-Leaderboard)
- [OpenRouter](https://openrouter.ai/)

## 📄 라이선스

Apache 2.0 License

## 🤝 기여

이슈와 PR을 환영합니다!

---

**Made with ❤️ for LLM Function Calling Evaluation**
