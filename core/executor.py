import json

class BFCLMockExecutor:
    """
    BFCL 멀티턴 테스트를 위해 도구 호출에 대한 가짜 피드백(Mock Response)을 제공합니다.
    실제 환경이 아니므로, 정답지(GT) 또는 초기 설정을 참고하여 적절한 메시지를 생성합니다.
    """
    def __init__(self, initial_config=None):
        self.config = initial_config or {}

    def execute(self, tool_call):
        func_name = tool_call.get("name") or list(tool_call.keys())[0]
        args = tool_call.get("arguments") or tool_call.get(func_name) or {}
        
        # 1. 파일 시스템 관련 (GorillaFileSystem)
        if "GorillaFileSystem" in func_name or func_name in ["ls", "cd", "mkdir", "cat", "grep", "mv", "cp"]:
            return self._handle_file_system(func_name, args)
        
        # 2. 검색 관련 (search_engine_query)
        if "search" in func_name:
            return self._handle_search(args)
            
        # 3. 기타 기본 응답
        return f"Successfully executed {func_name}. Result: [Mocked Success]"

    def _handle_file_system(self, func, args):
        # 단순 성공 메시지 반환 (상태 추적은 생략하고 모델이 다음 단계로 넘어가게 유도)
        if func in ["ls", "GorillaFileSystem.ls"]:
            return "total 2\ndrwxr-xr-x  2 user  staff  64 Jan 20 12:00 .\n-rw-r--r--  1 user  staff  1024 Jan 20 12:00 log.txt"
        if func in ["cat", "GorillaFileSystem.cat"]:
            return f"Content of {args.get('file_name', 'file')}: [Mocked File Content]"
        return f"Directory/File operation {func} completed."

    def _handle_search(self, args):
        query = args.get("keywords") or args.get("query") or ""
        # 특정 키워드에 대한 힌트 제공 (모델이 최종 정답에 가깝게 사고하도록)
        return f"Search result for '{query}': Found relevant information. Please proceed to the next step to extract the specific value."
