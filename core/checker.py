import json
import re
import ast

class BFCLChecker:
    """
    BFCL 표준을 준수하는 고도화된 체커.
    누적된 호출 기록과 최종 텍스트 답변을 모두 검증합니다.
    """
    @staticmethod
    def ast_checker(all_model_calls, ground_truth, last_content="", category=""):
        """
        all_model_calls: 대화 전체에서 발생한 모든 도구 호출 리스트
        ground_truth: 정답지
        last_content: 모델의 마지막 텍스트 응답
        category: 테스트 카테고리 (parallel 감지용)
        """
        if not ground_truth: return False, "❌ No Ground Truth"
        
        # 1. Relevance Match (문자열 정답인 경우 - web_search 등)
        if isinstance(ground_truth[0], str):
            # 호출 인자나 마지막 답변 내용 중 정답이 있는지 확인
            search_space = (str(all_model_calls) + " " + str(last_content)).lower()
            for gt in ground_truth:
                if gt.lower() in search_space:
                    return True, f"✅ Relevance Match: '{gt}' found"
            return False, f"❌ Answer mismatch (Expected: {ground_truth})"

        # 2. AST Match (도구 호출 구조 검증)
        # GT 평탄화
        flattened_gt = []
        for gt in ground_truth:
            if isinstance(gt, list): flattened_gt.extend(gt)
            else: flattened_gt.append(gt)

        # 도구 호출이 전혀 없는데 GT는 있는 경우
        if not all_model_calls and flattened_gt:
            return False, "❌ No tool calls generated"

        if len(all_model_calls) != len(flattened_gt):
            return False, f"⚠️ Count mismatch: Model({len(all_model_calls)}) vs GT({len(flattened_gt)})"

        # 3. Parallel 카테고리: 순서 무시 (BFCL 공식 표준)
        if "parallel" in category.lower():
            return BFCLChecker._parallel_checker_no_order(all_model_calls, flattened_gt)

        # 4. 일반 카테고리: 순서대로 매칭
        results = []
        all_pass = True
        
        for i, (m_call, g_call) in enumerate(zip(all_model_calls, flattened_gt)):
            match_result = BFCLChecker._single_call_checker(m_call, g_call, i)
            if not match_result["valid"]:
                all_pass = False
            results.append(match_result["message"])
                
        return all_pass, "\n".join(results)
    
    @staticmethod
    def _parallel_checker_no_order(all_model_calls, flattened_gt):
        """
        BFCL 공식 표준: 병렬 호출은 순서 무시
        GT를 하나씩 순회하며 모델 출력에서 매칭되는 것 찾기
        """
        matched_indices = []
        results = []
        all_pass = True
        
        for i, g_call in enumerate(flattened_gt):
            found_match = False
            
            for j, m_call in enumerate(all_model_calls):
                # 이미 매칭된 모델 출력은 스킵
                if j in matched_indices:
                    continue
                
                match_result = BFCLChecker._single_call_checker(m_call, g_call, i)
                if match_result["valid"]:
                    matched_indices.append(j)
                    results.append(match_result["message"])
                    found_match = True
                    break
            
            if not found_match:
                all_pass = False
                g_func = list(g_call.keys())[0]
                results.append(f"GT {i}: ❌ No match found for {g_func}")
        
        return all_pass, "\n".join(results)
    
    @staticmethod
    def _single_call_checker(m_call, g_call, index):
        """단일 함수 호출 검증"""
        m_func = list(m_call.keys())[0]
        g_func = list(g_call.keys())[0]
        
        # 함수명 비교 (유연하게)
        m_func_clean = m_func.replace("_", ".")
        g_func_clean = g_func.replace("_", ".")
        
        if m_func_clean != g_func_clean and m_func_clean.split('.')[-1] != g_func_clean.split('.')[-1]:
            return {
                "valid": False,
                "message": f"Step {index}: ❌ Name mismatch ({m_func} vs {g_func})"
            }
            
        m_params = m_call[m_func]
        g_params = g_call[g_func]
        param_errors = []
        
        for p_name, p_allowed in g_params.items():
            if p_name not in m_params:
                if isinstance(p_allowed, list) and any(v in [None, "", [], {}] for v in p_allowed):
                    continue
                param_errors.append(f"Missing '{p_name}'")
            elif not BFCLChecker._flexible_match(m_params[p_name], p_allowed):
                param_errors.append(f"Value error '{p_name}'")
        
        if not param_errors:
            return {"valid": True, "message": f"Step {index}: ✅ OK"}
        else:
            return {"valid": False, "message": f"Step {index}: " + ", ".join(param_errors)}

    @staticmethod
    def _flexible_match(m_val, p_allowed):
        """
        BFCL 표준: GT는 가능한 모든 답을 리스트로 표현
        예: GT가 {"param": [14, 15]}이면, 모델이 14나 15를 보내면 OK
        """
        # GT가 리스트가 아니면 리스트로 변환
        if not isinstance(p_allowed, list): 
            p_allowed = [p_allowed]
        
        # 각 허용된 값과 비교
        for a_val in p_allowed:
            # 1. Exact match
            if m_val == a_val: 
                return True
            
            # 2. Dict match (재귀적 비교)
            if isinstance(m_val, dict) and isinstance(a_val, dict):
                if BFCLChecker._dict_match(m_val, a_val):
                    return True
            
            # 3. List match (요소별 비교)
            if isinstance(m_val, list) and isinstance(a_val, list):
                if len(m_val) == len(a_val) and all(
                    BFCLChecker._flexible_match(m, a) for m, a in zip(m_val, a_val)
                ):
                    return True
            
            # 4. Numeric match (float comparison)
            try:
                if float(m_val) == float(a_val): 
                    return True
            except (ValueError, TypeError):
                pass
                
            # 5. String match (normalized)
            if str(m_val).strip().lower() == str(a_val).strip().lower(): 
                return True
                
        return False
    
    @staticmethod
    def _dict_match(m_dict, a_dict):
        """딕셔너리 재귀 비교"""
        # 모든 GT 키가 모델 출력에 있는지 확인
        for key, a_val in a_dict.items():
            if key not in m_dict:
                # GT에서 빈 값이 허용되는 경우 생략 가능
                if isinstance(a_val, list) and any(v in [None, "", [], {}] for v in a_val):
                    continue
                return False
            
            # 재귀적으로 값 비교
            if not BFCLChecker._flexible_match(m_dict[key], a_val):
                return False
        
        return True
