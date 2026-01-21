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
                        "include_thought": True
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
                if "429" in str(e) and attempt < max_retries - 1:
                    print(f"⚠️ Rate limited. Retrying in {retry_delay}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2 # Exponential backoff
                    continue
                raise Exception(f"Inference Failed: {str(e)}")

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
                except json.JSONDecodeError:
                    # JSON 파싱 실패 시 원본 문자열 유지
                    decoded_output.append({tc.function.name: tc.function.arguments})
                except Exception as e:
                    # 기타 에러 발생 시 로그 출력 및 원본 유지
                    print(f"⚠️ Decode AST Error: {e}")
                    decoded_output.append({tc.function.name: tc.function.arguments})
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
