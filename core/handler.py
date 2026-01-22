import json
import re
import time
from openai import OpenAI

class ModelHandler:
    """
    다이어그램의 'Handler' 역할을 수행합니다.
    Inference 엔드포인트 초기화 및 결과물 디코딩(AST, Executable)을 담당합니다.
    """
    def __init__(self, api_key, model_name, base_url="https://openrouter.ai/api/v1"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name
        self.name_map = {} # 치환된 이름 보관용

    def inference(self, messages, tools=None, temperature=0, force_tool=False, max_tokens=4096):
        """
        다이어그램의 handler.inference(data) 단계
        BFCL 표준을 따르는 모델 호출
        """
        start_time = time.time()
        sanitized_tools = self._prepare_tools(tools)

        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                params = {
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "extra_body": {
                        "include_reasoning": True,
                        "include_thought": True,
                        "route": "fallback"
                    }
                }
                
                # Tool calling 설정 (BFCL 표준)
                if sanitized_tools:
                    params["tools"] = sanitized_tools
                    params["tool_choice"] = "required" if force_tool else "auto"
                    
                response = self.client.chat.completions.create(**params)
                latency = (time.time() - start_time) * 1000
                
                msg = response.choices[0].message
                full_msg_dict = msg.model_dump()
                
                # 응답 검증 (디버깅용)
                self._validate_response(msg, sanitized_tools)
                
                # 사고 과정 추출
                thinking = self._extract_thinking(msg, full_msg_dict)

                return {
                    "raw_response": response,
                    "msg_obj": msg,
                    "content": msg.content or "",
                    "thinking": thinking,
                    "latency": round(latency, 2),
                    "tokens": response.usage.total_tokens if response.usage else 0
                }
            except Exception as e:
                error_str = str(e)
                # 429 (Rate limit) 또는 404 (Provider unavailable) 에러는 재시도
                if (("429" in error_str or "404" in error_str) and attempt < max_retries - 1):
                    error_type = "Rate limited" if "429" in error_str else "Provider unavailable (404)"
                    print(f"⚠️ {error_type}. Retrying in {retry_delay}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                # 마지막 시도 실패
                if "404" in error_str:
                    raise Exception(f"Inference Failed: Model '{self.model_name}' not available. All providers returned 404. Full error: {error_str}")
                raise Exception(f"Inference Failed: {error_str}")
    
    def _validate_response(self, msg, tools_provided):
        """
        응답 검증 및 디버깅 정보 출력
        BFCL 표준에 따른 응답 형식 확인
        """
        # Tool calls가 있는지 확인
        has_tool_calls = msg.tool_calls and len(msg.tool_calls) > 0
        has_content = msg.content and len(msg.content.strip()) > 0
        
        # 디버깅: Tool이 제공되었는데 tool_calls가 없는 경우
        if tools_provided and not has_tool_calls:
            if has_content:
                # Content에서 함수 호출을 찾을 수 있는지 체크
                if any(pattern in msg.content.lower() for pattern in ['<function>', 'arguments', '{']):
                    print(f"⚠️ Model returned tool call in content instead of tool_calls field")
                    print(f"   Content preview: {msg.content[:200]}")
                else:
                    print(f"⚠️ Model did not return any tool calls (tools were provided)")
        
        # 디버깅: Tool calls가 있지만 arguments가 비어있는 경우
        if has_tool_calls:
            for tc in msg.tool_calls:
                args_str = tc.function.arguments if hasattr(tc.function, 'arguments') else ""
                if not args_str or args_str.strip() in ["{", "{\"", "\"", ""]:
                    print(f"⚠️ Tool call '{tc.function.name}' has empty/incomplete arguments: '{args_str}'")
                    # Content도 함께 출력
                    if has_content:
                        print(f"   Content exists ({len(msg.content)} chars): {msg.content[:200]}")

    def decode_ast(self, inference_result):
        """
        다이어그램의 handler.decode_ast(model_output) 단계
        BFCL 표준을 따르는 함수 호출 파싱
        
        우선순위:
        1. Content에서 JSON 파싱 (Llama 등 prompt-based 모델)
        2. tool_calls 사용 (OpenAI 호환 모델)
        """
        msg = inference_result["msg_obj"]
        decoded_output = []
        
        # 1. 먼저 content에서 함수 호출 추출 시도 (Llama 우선)
        if msg.content and msg.content.strip():
            content_calls = self._extract_calls_from_content(msg.content)
            if content_calls:
                print(f"   ✅ Extracted {len(content_calls)} call(s) from content (Llama/prompt-based model)")
                return content_calls
        
        # 2. Content에서 추출 실패 시 표준 tool_calls 확인 (OpenAI 스타일)
        if msg.tool_calls:
            for tc in msg.tool_calls:
                san_name = tc.function.name
                orig_name = self.name_map.get(san_name, san_name)
                raw_args = tc.function.arguments
                
                # 불완전한 arguments 감지 (OpenRouter 변환 실패)
                raw_args_stripped = raw_args.strip() if raw_args else ""
                incomplete_patterns = ["{", "{\"", "{\"\"", "\"", "{\n"]
                
                if raw_args_stripped in incomplete_patterns:
                    print(f"⚠️ Skipping incomplete tool_call '{orig_name}': arguments='{raw_args_stripped}'")
                    # Content가 있었다면 이미 위에서 처리됨
                    continue
                
                # 파싱 시도
                parsed_args = self._parse_arguments_robust(raw_args, orig_name)
                decoded_output.append({orig_name: parsed_args})
        
        return decoded_output
    
    def _parse_arguments_robust(self, raw_args, func_name):
        """
        인자를 robust하게 파싱 (BFCL 표준)
        
        여러 복구 전략을 시도:
        1. 표준 JSON 파싱
        2. 빈/불완전 JSON 체크
        3. 작은따옴표 변환
        4. 불완전한 JSON 완성
        5. 특수 포맷 처리
        """
        # 빈 값 체크
        if not raw_args or not raw_args.strip():
            return {}
        
        raw_args_stripped = raw_args.strip()
        
        # 명확히 불완전한 JSON (decode_ast에서 이미 처리됨)
        incomplete_patterns = ["{", "{\"", "{\"\"", "\"", "{\n", "null", "None"]
        if raw_args_stripped in incomplete_patterns:
            return {}
        
        # 표준 JSON 파싱 시도
        try:
            args = json.loads(raw_args)
            return args if isinstance(args, dict) else {}
        except json.JSONDecodeError:
            pass
        
        # 복구 전략들
        recovery_strategies = [
            # 1. 작은따옴표를 큰따옴표로
            lambda s: s.replace("'", '"'),
            # 2. 닫는 중괄호 추가
            lambda s: s.rstrip(',').rstrip() + '}' if not s.rstrip().endswith('}') else s,
            # 3. 열린 중괄호만 있는 경우
            lambda s: '{}' if s.strip() == '{' else s,
            # 4. 백슬래시 이스케이프 처리
            lambda s: s.replace('\\"', '"').replace('\\n', '\n'),
        ]
        
        for i, strategy in enumerate(recovery_strategies):
            try:
                fixed = strategy(raw_args)
                if fixed != raw_args:  # 변경이 있었다면
                    args = json.loads(fixed)
                    if isinstance(args, dict):
                        print(f"   ✅ Recovered {func_name} args using strategy {i+1}")
                        return args
            except:
                continue
        
        # 모든 전략 실패
        print(f"❌ Failed to parse arguments for {func_name}")
        print(f"   Raw: {raw_args[:150]}")
        return {}
    
    def _extract_calls_from_content(self, content):
        """
        content 필드에서 함수 호출 추출 (Llama 등 프롬프트 기반 모델용)
        
        BFCL 표준에서 프롬프트 기반 모델들은 다음과 같은 포맷을 사용:
        1. Llama 스타일: {"name": "func_name", "parameters": {...}}
        2. 배열 스타일: [{"name": "func_name", "parameters": {...}}, ...]
        3. XML 스타일: <function>...</function><parameters>...</parameters>
        4. Python 호출 스타일: func_name({...})
        """
        decoded_output = []
        
        if not content or not content.strip():
            return decoded_output
        
        content = content.strip()
        
        # 패턴 1: Llama/BFCL 표준 JSON 포맷 (최우선)
        # {"name": "func_name", "parameters": {...}} 또는 [{"name": ..., "parameters": ...}]
        try:
            # JSON 추출 시도 (코드 블록이나 마크다운 제거)
            json_content = content
            
            # 코드 블록 제거 (```json ... ```)
            code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
            if code_block_match:
                json_content = code_block_match.group(1).strip()
            
            # JSON 파싱
            parsed = json.loads(json_content)
            
            # 단일 딕셔너리: {"name": "...", "parameters": {...}}
            if isinstance(parsed, dict):
                if 'name' in parsed:
                    func_name = parsed['name']
                    orig_name = self.name_map.get(func_name, func_name)
                    # "parameters" 또는 "arguments" 키 지원
                    params = parsed.get('parameters', parsed.get('arguments', {}))
                    decoded_output.append({orig_name: params})
                    return decoded_output
            
            # 배열: [{"name": "...", "parameters": {...}}, ...]
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and 'name' in item:
                        func_name = item['name']
                        orig_name = self.name_map.get(func_name, func_name)
                        params = item.get('parameters', item.get('arguments', {}))
                        decoded_output.append({orig_name: params})
                if decoded_output:
                    return decoded_output
        except json.JSONDecodeError:
            pass
        except Exception:
            pass
        
        # 패턴 2: 세미콜론으로 구분된 Llama 다중 호출
        # {"name": "func1", "parameters": {...}}; {"name": "func2", "parameters": {...}}
        if ';' in content and '{' in content:
            try:
                parts = content.split(';')
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    parsed = json.loads(part)
                    if isinstance(parsed, dict) and 'name' in parsed:
                        func_name = parsed['name']
                        orig_name = self.name_map.get(func_name, func_name)
                        params = parsed.get('parameters', parsed.get('arguments', {}))
                        decoded_output.append({orig_name: params})
                if decoded_output:
                    return decoded_output
            except:
                pass
        
        # 패턴 3: XML 스타일 (<function>...</function>)
        function_pattern = r'<function>(.*?)</function>\s*<parameters>(.*?)</parameters>'
        matches = re.finditer(function_pattern, content, re.DOTALL)
        for match in matches:
            func_name = match.group(1).strip()
            params_str = match.group(2).strip()
            orig_name = self.name_map.get(func_name, func_name)
            args = self._parse_arguments_robust(params_str, orig_name)
            decoded_output.append({orig_name: args})
        
        if decoded_output:
            return decoded_output
        
        # 패턴 4: Python 호출 스타일 (func_name({...}))
        func_call_pattern = r'(\w+)\s*\(\s*(\{[^}]*\})\s*\)'
        matches = re.finditer(func_call_pattern, content)
        for match in matches:
            func_name = match.group(1)
            params_str = match.group(2)
            orig_name = self.name_map.get(func_name, func_name)
            args = self._parse_arguments_robust(params_str, orig_name)
            decoded_output.append({orig_name: args})
        
        return decoded_output

    def decode_executable(self, inference_result):
        """다이어그램의 handler.decode_executable(model_output) 단계"""
        ast_output = self.decode_ast(inference_result)
        executable_output = []
        
        for call in ast_output:
            for name, params in call.items():
                if isinstance(params, dict):
                    args_str = ", ".join([f"{k}={repr(v)}" for k, v in params.items()])
                    executable_output.append(f"{name}({args_str})")
                else:
                    executable_output.append(f"{name}({params})")
        return executable_output

    def _prepare_tools(self, tools):
        if not tools: return None
        sanitized = []
        self.name_map = {}
        
        def sanitize_schema(schema):
            if isinstance(schema, dict):
                new_schema = schema.copy()
                
                # Handle "type" field
                if "type" in new_schema:
                    type_value = new_schema["type"]
                    
                    # 1. Handle "any" type (non-standard) - remove the type field
                    if type_value == "any":
                        del new_schema["type"]
                    # 2. Handle uppercase types (String, Boolean, etc.)
                    elif isinstance(type_value, str):
                        # Convert to lowercase first
                        type_lower = type_value.lower()
                        
                        # Type mapping for non-standard JSON Schema types used in BFCL
                        type_mapping = {
                            "dict": "object",
                            "float": "number",
                            "int": "integer",
                            "list": "array",
                            "bool": "boolean",
                            # Standard types (already lowercase)
                            "string": "string",
                            "number": "number",
                            "integer": "integer",
                            "object": "object",
                            "array": "array",
                            "boolean": "boolean",
                            "null": "null"
                        }
                        
                        if type_lower in type_mapping:
                            new_schema["type"] = type_mapping[type_lower]
                        else:
                            # Unknown type, remove it
                            del new_schema["type"]
                
                # Recursively sanitize nested properties
                if "properties" in new_schema:
                    new_schema["properties"] = {k: sanitize_schema(v) for k, v in new_schema["properties"].items()}
                if "items" in new_schema:
                    new_schema["items"] = sanitize_schema(new_schema["items"])
                return new_schema
            return schema

        for f in tools:
            orig_name = f["name"]
            # OpenAI는 점(.)을 허용하지 않으므로 언더바(_)로 치환
            san_name = orig_name.replace(".", "_")
            self.name_map[san_name] = orig_name
            
            sanitized.append({
                "type": "function",
                "function": {
                    "name": san_name,
                    "description": f.get("description", ""),
                    "parameters": sanitize_schema(f["parameters"])
                }
            })
        return sanitized

    def _extract_thinking(self, msg, full_msg_dict):
        thinking = ""
        for field in ['reasoning', 'thought', 'thinking_process']:
            val = full_msg_dict.get(field) or (msg.model_extra.get(field) if hasattr(msg, 'model_extra') else None)
            if val and isinstance(val, str) and val.strip():
                thinking = val
                break
        if not thinking and msg.content and "<thought>" in msg.content:
            match = re.search(r"<thought>(.*?)</thought>", msg.content, re.DOTALL | re.IGNORECASE)
            if match: thinking = match.group(1).strip()
        return thinking if thinking else "N/A"
