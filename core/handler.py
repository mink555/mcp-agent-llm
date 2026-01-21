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

    def inference(self, messages, tools=None, temperature=0, force_tool=False):
        """다이어그램의 handler.inference(data) 단계"""
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
                    "extra_body": {
                        "include_reasoning": True,
                        "include_thought": True,
                        # OpenRouter: provider fallback 활성화
                        "route": "fallback"
                    }
                }
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
                    retry_delay *= 2 # Exponential backoff
                    continue
                # 마지막 시도 실패 또는 재시도 불가능한 에러
                if "404" in error_str:
                    raise Exception(f"Inference Failed: Model '{self.model_name}' not available. All providers returned 404. Full error: {error_str}")
                raise Exception(f"Inference Failed: {error_str}")

    def decode_ast(self, inference_result):
        """다이어그램의 handler.decode_ast(model_output) 단계"""
        msg = inference_result["msg_obj"]
        decoded_output = []
        
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    san_name = tc.function.name
                    orig_name = self.name_map.get(san_name, san_name)
                    args = json.loads(tc.function.arguments)
                    decoded_output.append({orig_name: args})
                except json.JSONDecodeError as e:
                    # JSON 파싱 실패 시 빈 딕셔너리로 처리
                    print(f"⚠️ JSON Decode Error for {tc.function.name}: {str(e)[:100]}")
                    print(f"   Raw arguments: {tc.function.arguments[:200]}")
                    # 문자열을 파싱 시도
                    try:
                        # 작은따옴표를 큰따옴표로 변환 후 재시도
                        fixed_args = tc.function.arguments.replace("'", '"')
                        args = json.loads(fixed_args)
                        decoded_output.append({tc.function.name: args})
                    except:
                        # 완전히 실패하면 빈 딕셔너리
                        decoded_output.append({tc.function.name: {}})
                except Exception as e:
                    # 기타 에러 발생 시 로그 출력 및 빈 딕셔너리
                    print(f"⚠️ Decode AST Error: {e}")
                    decoded_output.append({tc.function.name: {}})
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
                # Type mapping for non-standard JSON Schema types used in BFCL
                type_mapping = {
                    "dict": "object",
                    "float": "number",
                    "int": "integer",
                    "list": "array",
                    "bool": "boolean"
                }
                if new_schema.get("type") in type_mapping:
                    new_schema["type"] = type_mapping[new_schema["type"]]
                
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
