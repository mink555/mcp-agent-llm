import json
from pathlib import Path

class BFCLDataLoader:
    def __init__(self, data_root="berkeley-function-call-leaderboard/bfcl_eval/data"):
        self.data_root = Path(data_root)
        self.ans_root = self.data_root / "possible_answer"

    def load_dataset(self, category, limit=None):
        data_path = self.data_root / f"BFCL_v4_{category}.json"
        ans_path = self.ans_root / f"BFCL_v4_{category}.json"
        
        if not data_path.exists() or not ans_path.exists():
            return None, None
            
        with open(data_path, 'r', encoding='utf-8') as f:
            questions = [json.loads(line) for line in f.readlines()]
            if limit: questions = questions[:limit]
            
        with open(ans_path, 'r', encoding='utf-8') as f:
            answers = [json.loads(line) for line in f.readlines()]
            if limit: answers = answers[:limit]
            
        return questions, answers

    def is_multi_turn(self, category):
        return "multi_turn" in category or "web_search" in category

    def get_functions(self, category, question_data):
        if 'function' in question_data:
            return question_data['function']
        
        # Agentic/Multi-turn 카테고리의 경우 외부 파일 참조
        func_doc_path = self.data_root / "multi_turn_func_doc" / f"{category}.json"
        if func_doc_path.exists():
            with open(func_doc_path, 'r', encoding='utf-8') as f:
                # 첫 번째 줄만 읽어서 처리 (JSONL 기준)
                line = f.readline()
                if line: return [json.loads(line)]
        return []
