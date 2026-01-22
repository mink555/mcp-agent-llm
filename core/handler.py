import json
import re
import time
from openai import OpenAI

class ModelHandler:
    """
    BFCL 표준 Handler: 네이티브 OpenAI tool_calls만 사용
    Inference 엔드포인트 초기화 및 결과물 디코딩(AST, Executable)을 담당합니다.
    """
    def __init__(self, api_key, model_name, base_url="https://openrouter.ai/api/v1"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name
        self.name_map = {}

    def inference(self, messages, tools=None, temperature=0, force_tool=False, max_tokens=4096):
        """
        BFCL 표준 inference: OpenAI 호환 tool_calls API 사용
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

    def decode_ast(self, inference_result):
        """
        BFCL 표준: 네이티브 OpenAI tool_calls만 사용
        """
        msg = inference_result["msg_obj"]
        decoded_output = []
        
        # 네이티브 tool_calls만 처리
        if not msg.tool_calls:
            return decoded_output
        
        for tc in msg.tool_calls:
            san_name = tc.function.name
            orig_name = self.name_map.get(san_name, san_name)
            raw_args = tc.function.arguments
            
            # Arguments 파싱
            parsed_args = self._parse_arguments(raw_args, orig_name)
            decoded_output.append({orig_name: parsed_args})
        
        return decoded_output
    
    def _parse_arguments(self, raw_args, func_name):
        """
        Arguments 파싱 (BFCL 표준)
        """
        # 빈 값
        if not raw_args or not raw_args.strip():
            return {}
        
        raw_args_stripped = raw_args.strip()
        
        # 불완전한 JSON
        incomplete_patterns = ["{", "{\"", "{\"\"", "\"", "{\n", "null", "None"]
        if raw_args_stripped in incomplete_patterns:
            return {}
        
        # JSON 파싱 시도
        try:
            args = json.loads(raw_args)
            return args if isinstance(args, dict) else {}
        except json.JSONDecodeError:
            pass
        
        # 복구 전략
        recovery_strategies = [
            lambda s: s.replace("'", '"'),  # 작은따옴표 → 큰따옴표
            lambda s: s.rstrip(',').rstrip() + '}' if not s.rstrip().endswith('}') else s,  # 닫는 중괄호
        ]
        
        for strategy in recovery_strategies:
            try:
                fixed = strategy(raw_args)
                if fixed != raw_args:
                    args = json.loads(fixed)
                    if isinstance(args, dict):
                        return args
            except:
                continue
        
        # 파싱 실패
        return {}

    def decode_executable(self, inference_result):
        """Executable 형식으로 변환"""
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
        """Tools를 OpenAI 표준 형식으로 변환"""
        if not tools:
            return None
        
        sanitized = []
        self.name_map = {}
        
        def sanitize_schema(schema):
            if isinstance(schema, dict):
                new_schema = schema.copy()
                
                # Type 필드 처리
                if "type" in new_schema:
                    type_value = new_schema["type"]
                    
                    # "any" 타입 제거
                    if type_value == "any":
                        del new_schema["type"]
                    # 대문자 타입 변환
                    elif isinstance(type_value, str):
                        type_lower = type_value.lower()
                        
                        type_mapping = {
                            "dict": "object",
                            "float": "number",
                            "int": "integer",
                            "list": "array",
                            "bool": "boolean",
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
                            del new_schema["type"]
                
                # 재귀적으로 sanitize
                if "properties" in new_schema:
                    new_schema["properties"] = {k: sanitize_schema(v) for k, v in new_schema["properties"].items()}
                if "items" in new_schema:
                    new_schema["items"] = sanitize_schema(new_schema["items"])
                return new_schema
            return schema

        for f in tools:
            orig_name = f["name"]
            # 점(.)을 언더바(_)로 치환 (OpenAI 호환)
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
        """사고 과정 추출"""
        thinking = ""
        for field in ['reasoning', 'thought', 'thinking_process']:
            val = full_msg_dict.get(field) or (msg.model_extra.get(field) if hasattr(msg, 'model_extra') else None)
            if val and isinstance(val, str) and val.strip():
                thinking = val
                break
        if not thinking and msg.content and "<thought>" in msg.content:
            match = re.search(r"<thought>(.*?)</thought>", msg.content, re.DOTALL | re.IGNORECASE)
            if match:
                thinking = match.group(1).strip()
        return thinking if thinking else "N/A"
