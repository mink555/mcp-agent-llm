import json
from pathlib import Path

class BFCLDataLoader:
    def __init__(self, data_root="berkeley-function-call-leaderboard/bfcl_eval/data"):
        self.data_root = Path(data_root)
        self.ans_root = self.data_root / "possible_answer"

    def load_dataset(self, category, limit=None):
        data_path = self.data_root / f"BFCL_v4_{category}.json"
        ans_path = self.ans_root / f"BFCL_v4_{category}.json"
        
        # Question 파일이 없으면 None 반환
        if not data_path.exists():
            return None, None
            
        # Question 파일 로드
        with open(data_path, 'r', encoding='utf-8') as f:
            questions = [json.loads(line) for line in f.readlines()]
            if limit: questions = questions[:limit]
        
        # Possible answer 파일이 없는 경우: ground_truth를 question에서 추출
        # (irrelevance, live_irrelevance, live_relevance, format_sensitivity)
        if not ans_path.exists():
            # ground_truth가 question 내부에 있는 경우
            answers = []
            for q in questions:
                if 'ground_truth' in q:
                    answers.append({'ground_truth': q['ground_truth']})
                else:
                    # ground_truth가 없으면 빈 리스트로 가정 (relevance 카테고리)
                    answers.append({'ground_truth': []})
            return questions, answers
            
        # Possible answer 파일이 있는 경우: 정답 로드
        with open(ans_path, 'r', encoding='utf-8') as f:
            answers = [json.loads(line) for line in f.readlines()]
            if limit: answers = answers[:limit]
            
        return questions, answers

    def is_multi_turn(self, category):
        return "multi_turn" in category or "web_search" in category

    def get_functions(self, category, question_data):
        if 'function' in question_data:
            return question_data['function']
        
        # Multi-turn/Agentic 카테고리: involved_classes 기반으로 함수 로드
        if 'involved_classes' in question_data:
            all_functions = []
            for class_name in question_data['involved_classes']:
                # 클래스명을 snake_case 파일명으로 변환
                # GorillaFileSystem -> gorilla_file_system
                file_name = self._class_to_filename(class_name)
                func_doc_path = self.data_root / "multi_turn_func_doc" / f"{file_name}.json"
                
                if func_doc_path.exists():
                    with open(func_doc_path, 'r', encoding='utf-8') as f:
                        # JSONL 형식: 각 줄이 하나의 함수
                        for line in f:
                            if line.strip():
                                all_functions.append(json.loads(line))
            return all_functions
        
        return []
    
    def _class_to_filename(self, class_name):
        """클래스명을 파일명으로 변환 (예: GorillaFileSystem -> gorilla_file_system)"""
        # 특수 케이스 매핑 (실제 파일명과 클래스명이 다른 경우)
        special_mapping = {
            'TwitterAPI': 'posting_api',
            'MessageAPI': 'message_api',
        }
        
        if class_name in special_mapping:
            return special_mapping[class_name]
        
        # 일반 케이스: CamelCase -> snake_case
        import re
        # 대문자 앞에 언더스코어 추가 (첫 글자 제외)
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', class_name)
        # 연속된 대문자와 소문자 사이에 언더스코어 추가
        result = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        return result
