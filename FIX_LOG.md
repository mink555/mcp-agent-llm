# 버그 수정 로그

## 날짜: 2026-01-21

## 수정된 이슈

### 1. Mistral API 400 에러: Tool Schema Validation 실패

#### 문제
- Mistral API가 tool schema에서 비표준 JSON Schema 타입을 거부
- 에러 메시지: `"Invalid tool schema: 'String' is not valid"`, `"Invalid tool schema: 'Boolean' is not valid"`, `"Invalid tool schema: 'any' is not valid"`
- BFCL 데이터셋의 일부 함수 정의가 대문자 타입(`String`, `Boolean`) 또는 비표준 타입(`any`)을 사용

#### 원인
```python
# 기존 코드 (handler.py)
type_mapping = {
    "dict": "object",
    "float": "number",
    "int": "integer",
    "list": "array",
    "bool": "boolean"
}
# 문제: "String", "Boolean", "any" 같은 케이스를 처리하지 못함
```

#### 해결 방법
`core/handler.py`의 `sanitize_schema` 함수를 다음과 같이 강화:

1. **대문자 타입 정규화**
   - `String` → `string`
   - `Boolean` → `boolean`
   - `Integer` → `integer`
   - 모든 타입을 소문자로 변환 후 매핑

2. **"any" 타입 처리**
   - JSON Schema에 `any` 타입은 존재하지 않음
   - Mistral API 호환을 위해 `type` 필드 자체를 제거
   - 또는 모든 타입을 허용하는 방식으로 변환

3. **알 수 없는 타입 처리**
   - 매핑에 없는 타입이 들어오면 `type` 필드 제거

#### 참고 자료
- [Mistral API Function Calling Docs](https://docs.mistral.ai/capabilities/function_calling)
- [JSON Schema Specification](https://json-schema.org/understanding-json-schema/reference/type)
- Mistral은 OpenAI 호환 API를 제공하지만, tool schema validation이 더 엄격함

---

### 2. Memory/Web Search 카테고리 0% 정확도 문제

#### 문제
- `memory`와 `web_search` 카테고리에서 모든 테스트 케이스가 실패 (0% 정확도)
- 두 카테고리 모두 AGENTIC 그룹에 속함

#### 원인 분석

**Memory 카테고리**:
- Memory 카테고리는 "prerequisite conversation"이 필요
- 예시:
  ```
  1. Prerequisite: 사용자가 "내 이름은 Michael이야" 라고 말함 → 메모리에 저장
  2. 실제 질문: "내 이름이 뭐지?" → 메모리에서 검색 → "Michael"
  ```
- 기존 코드는 prerequisite conversation을 실행하지 않아서 메모리가 비어있음
- 따라서 모델이 "Michael"을 찾을 수 없어서 실패

**Web Search 카테고리**:
- 복잡한 multi-hop 질문 (예: "2024년 가장 비싼 차를 생산한 나라의 대통령은 누구?")
- 여러 단계의 웹 검색과 추론이 필요
- 최종 답변에 정답 문자열이 포함되어야 통과
- 현재 시스템 프롬프트가 최적화되지 않았을 가능성

#### 해결 방법

**Memory 카테고리 수정**:

1. **Prerequisite Conversation 로드 및 실행**
   ```python
   # memory_prereq_conversation/{scenario}.json 파일 로드
   # 예: memory_customer.json, memory_healthcare.json
   
   # Prerequisite conversation을 먼저 실행하여 메모리에 정보 저장
   for prereq_turn in prereq_turns:
       # 모델 호출 → 메모리 저장 함수 실행
       # 예: core_memory_add(text="My name is Michael")
   ```

2. **데이터 구조**
   ```json
   {
     "id": "memory_prereq_0-customer-0",
     "question": [[
       {"role": "user", "content": "My name is Michael..."}
     ]],
     "involved_classes": ["MemoryAPI"],
     "scenario": "customer"
   }
   ```

3. **실행 흐름**
   ```
   Test ID: memory_0-customer-0
   ↓
   1. prerequisite conversation 찾기 (memory_prereq_0-customer-0)
   2. prerequisite 실행 → 메모리에 정보 저장
   3. 실제 질문 실행 → 메모리에서 정보 검색
   4. 답변 확인: ground_truth에 정답이 있는지 체크
   ```

**Web Search 카테고리**:
- Memory 수정이 우선, web_search는 시스템 프롬프트 개선이 필요할 수 있음
- Web search는 실제 API 호출이 필요할 수 있어 추가 조사 필요

#### 수정 파일
- `main.py`: `process_test_case` 함수에 prerequisite conversation 로직 추가
- Memory 데이터 로드 및 실행 로직 구현

---

## 테스트 방법

### 1. Mistral API 수정 검증
```bash
# Mistral 모델로 빠른 테스트
python main.py --model "mistralai/mistral-small-3.2-24b-instruct" --categories simple_python --samples 2

# 400 에러 없이 정상 실행되는지 확인
```

### 2. Memory 카테고리 검증
```bash
# Memory 카테고리 테스트
python main.py --model "mistralai/mistral-small-3.2-24b-instruct" --categories memory --samples 5

# 정확도가 0%에서 개선되는지 확인
```

---

## 향후 개선 사항

1. **Web Search 카테고리 최적화**
   - 시스템 프롬프트에 multi-hop reasoning 가이드 추가
   - 웹 검색 결과 파싱 로직 검증

2. **Tool Schema Validation 테스트**
   - 모든 BFCL 데이터셋의 함수 정의를 스캔하여 비표준 타입 확인
   - 자동 테스트 추가

3. **에러 로깅 개선**
   - Tool schema validation 실패 시 상세한 에러 로그 출력
   - 어떤 함수의 어떤 파라미터가 문제인지 명시

---

## 참고

### BFCL 공식 표준
- [BFCL GitHub](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard)
- [BFCL 공식 웹사이트](https://gorilla.cs.berkeley.edu/leaderboard.html)

### Mistral API 문서
- [Function Calling](https://docs.mistral.ai/capabilities/function_calling)
- [API Specs](https://docs.mistral.ai/api)

### JSON Schema 표준
- [JSON Schema Type Reference](https://json-schema.org/understanding-json-schema/reference/type)
- 표준 타입: `string`, `number`, `integer`, `object`, `array`, `boolean`, `null`
- 모두 **소문자**여야 함
