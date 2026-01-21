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
        category: 테스트 카테고리
        """
        # Ground truth가 None이거나 존재하지 않는 경우에만 에러
        if ground_truth is None: 
            return False, "❌ No Ground Truth"
        
        # 1. Irrelevance detection: GT가 빈 리스트 → 함수 호출 없어야 함
        if not ground_truth or (isinstance(ground_truth, list) and len(ground_truth) == 0):
            if not all_model_calls:
                return True, "✅ Irrelevance: No function calls (correct)"
            else:
                return False, f"❌ Irrelevance: Model called {len(all_model_calls)} functions (should be 0)"
        
        # 2. Multi-turn: GT가 문자열 리스트인 경우 (BFCL 공식 형식)
        # GT: [["cd(folder='document')", "mkdir(dir_name='temp')"], ...]
        if ground_truth and isinstance(ground_truth[0], list) and ground_truth[0] and isinstance(ground_truth[0][0], str):
            # multi_turn은 문자열 형식이므로 executable로 변환하여 비교
            return BFCLChecker._multi_turn_string_checker(all_model_calls, ground_truth, category)
        
        # 3. Agentic (web_search, memory): Exact-match (문자열 정답)
        if isinstance(ground_truth[0], str):
            # 호출 인자나 마지막 답변 내용 중 정답이 있는지 확인
            search_space = (str(all_model_calls) + " " + str(last_content)).lower()
            for gt in ground_truth:
                if gt.lower() in search_space:
                    return True, f"✅ Exact Match: '{gt}' found"
            return False, f"❌ Answer mismatch (Expected: {ground_truth})"

        # 3. AST Match (도구 호출 구조 검증)
        # GT 평탄화
        flattened_gt = []
        for gt in ground_truth:
            if isinstance(gt, list): flattened_gt.extend(gt)
            else: flattened_gt.append(gt)

        # 3-1. GT가 빈 리스트인 경우 (이미 위에서 처리됨, 안전을 위한 체크)
        if not flattened_gt:
            if not all_model_calls:
                return True, "✅ No function calls expected (correct)"
            else:
                return False, f"❌ Model called {len(all_model_calls)} functions (should be 0)"

        # 2-2. Relevance detection: GT가 특별한 값 → 최소 1개 함수 호출만 확인
        if len(flattened_gt) == 1 and flattened_gt[0] in [{}, {"ANY": {}}]:
            if all_model_calls:
                return True, f"✅ Relevance: Model called {len(all_model_calls)} function(s) (correct)"
            else:
                return False, "❌ Relevance: No function calls (should have at least 1)"

        # 2-3. Multi-turn: Response-based (최소 필수 경로, 중복 허용)
        if "multi_turn" in category:
            return BFCLChecker._response_based_checker(all_model_calls, flattened_gt)

        # 2-4. Single-turn: Exact count match (기존 로직)
        if not all_model_calls:
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
    def _multi_turn_string_checker(all_model_calls, ground_truth, category):
        """
        Multi-turn GT가 문자열 형식인 경우 처리
        GT: [["cd(folder='document')", "mkdir(dir_name='temp')"], ...]
        Model: [{"cd": {"folder": "document"}}, {"mkdir": {"dir_name": "temp"}}, ...]
        """
        # GT를 평탄화 (모든 턴의 모든 호출을 하나의 리스트로)
        flattened_gt_strings = []
        for turn in ground_truth:
            if isinstance(turn, list):
                flattened_gt_strings.extend(turn)
            else:
                flattened_gt_strings.append(turn)
        
        if not flattened_gt_strings:
            return True, "✅ Empty GT"
        
        if not all_model_calls:
            return False, "❌ No tool calls generated"
        
        # 모델 호출을 문자열로 변환
        model_call_strings = []
        for call in all_model_calls:
            if isinstance(call, dict):
                # {"function_name": {"param": "value"}} -> "function_name(param='value')"
                func_name = list(call.keys())[0]
                params = call[func_name]
                if isinstance(params, dict):
                    param_strs = [f"{k}={repr(v)}" for k, v in params.items()]
                    model_call_strings.append(f"{func_name}({','.join(param_strs)})")
                else:
                    model_call_strings.append(f"{func_name}({params})")
            elif isinstance(call, str):
                model_call_strings.append(call)
        
        # 각 GT 호출이 모델 출력에 있는지 확인 (유연한 매칭)
        matched = 0
        results = []
        for i, gt_str in enumerate(flattened_gt_strings):
            found = False
            # GT 문자열에서 함수명 추출
            gt_func = gt_str.split('(')[0] if '(' in gt_str else gt_str
            
            for j, model_str in enumerate(model_call_strings):
                model_func = model_str.split('(')[0] if '(' in model_str else model_str
                
                # 함수명이 일치하면 매칭으로 간주 (파라미터는 유연하게)
                if gt_func.lower() == model_func.lower():
                    matched += 1
                    results.append(f"GT {i}: ✅ '{gt_func}' found")
                    found = True
                    break
            
            if not found:
                results.append(f"GT {i}: ❌ '{gt_func}' not found in model output")
        
        accuracy = (matched / len(flattened_gt_strings)) * 100 if flattened_gt_strings else 0
        
        if matched == len(flattened_gt_strings):
            return True, f"✅ All {matched} calls matched ({accuracy:.0f}%)"
        else:
            return False, f"⚠️ {matched}/{len(flattened_gt_strings)} calls matched ({accuracy:.0f}%)\n" + "\n".join(results[:5])
    
    @staticmethod
    def _response_based_checker(all_model_calls, flattened_gt):
        """
        BFCL 공식 Multi-turn 평가: Response-based evaluation
        최소 필수 경로 (minimum necessary path) 확인 + 중복 단계 허용
        
        GT의 모든 함수 호출이 모델 출력에 포함되는지 확인 (순서 무시, 중복 허용)
        """
        if not all_model_calls:
            return False, "❌ No tool calls generated"
        
        matched_indices = []
        results = []
        all_pass = True
        
        for i, g_call in enumerate(flattened_gt):
            found_match = False
            
            for j, m_call in enumerate(all_model_calls):
                # Response-based: 중복 허용 (이미 매칭된 것도 재사용 가능)
                match_result = BFCLChecker._single_call_checker(m_call, g_call, i)
                if match_result["valid"]:
                    matched_indices.append(j)
                    results.append(f"GT {i}: ✅ Found at Model[{j}]")
                    found_match = True
                    break
            
            if not found_match:
                all_pass = False
                g_func = list(g_call.keys())[0]
                results.append(f"GT {i}: ❌ Required call '{g_func}' not found")
        
        if all_pass:
            coverage = len(matched_indices) / len(flattened_gt) * 100
            extra_calls = len(all_model_calls) - len(set(matched_indices))
            msg = f"✅ All {len(flattened_gt)} required calls found (Coverage: {coverage:.0f}%)"
            if extra_calls > 0:
                msg += f" + {extra_calls} extra calls (allowed)"
            return True, msg
        else:
            return False, "\n".join(results)
    
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
        # 타입 검증: m_call이 딕셔너리가 아닌 경우 처리
        if not isinstance(m_call, dict):
            return {
                "valid": False,
                "message": f"Step {index}: ❌ Invalid call format (expected dict, got {type(m_call).__name__})"
            }
        
        if not m_call:
            return {
                "valid": False,
                "message": f"Step {index}: ❌ Empty call"
            }
        
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
        
        # m_params가 딕셔너리가 아닌 경우 처리
        if not isinstance(m_params, dict):
            return {
                "valid": False,
                "message": f"Step {index}: ❌ Invalid params format (expected dict, got {type(m_params).__name__})"
            }
        
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
