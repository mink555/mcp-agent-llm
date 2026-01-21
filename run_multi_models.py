#!/usr/bin/env python3
"""
다중 모델 벤치마크 실행 스크립트

20개 카테고리에 대해 샘플 10개씩 5개 모델을 순차 실행합니다.
"""

import os
import time
from datetime import datetime
from main import run_benchmark, DEFAULT_CONFIG, BFCL_ALL_CATEGORIES

# 테스트할 모델 목록
MODELS_TO_TEST = [
    "meta-llama/llama-3.3-70b-instruct",
    "mistralai/mistral-small-3.2-24b-instruct",
    "qwen/qwen3-32b",
    "qwen/qwen3-14b",  # 주의: "Paid model training" 정책 필요. Privacy 설정 확인: https://openrouter.ai/settings/privacy
    "qwen/qwen3-next-80b-a3b-instruct",
]

def run_multi_model_benchmark():
    """다중 모델 벤치마크 실행"""
    print("=" * 80)
    print("🚀 다중 모델 벤치마크 시작")
    print("=" * 80)
    print(f"📋 테스트 모델 수: {len(MODELS_TO_TEST)}개")
    print(f"📂 카테고리 수: {len(BFCL_ALL_CATEGORIES)}개 (20개)")
    print(f"📊 카테고리당 샘플: 10개")
    print(f"🎯 총 예상 테스트: {len(MODELS_TO_TEST)} × {len(BFCL_ALL_CATEGORIES)} × 10 = {len(MODELS_TO_TEST) * len(BFCL_ALL_CATEGORIES) * 10}개")
    print("=" * 80)
    print("\n테스트할 모델 목록:")
    for i, model in enumerate(MODELS_TO_TEST, 1):
        print(f"  {i}. {model}")
    print("\n" + "=" * 80)
    
    start_time = time.time()
    results_summary = []
    
    for model_idx, model_name in enumerate(MODELS_TO_TEST, 1):
        print(f"\n{'=' * 80}")
        print(f"[{model_idx}/{len(MODELS_TO_TEST)}] 모델: {model_name}")
        print(f"{'=' * 80}")
        
        model_start = time.time()
        
        # 벤치마크 설정
        config = {
            **DEFAULT_CONFIG,
            "model_name": model_name,
            "categories": list(BFCL_ALL_CATEGORIES.keys()),  # 전체 20개 카테고리
            "samples_per_cat": 10,  # 각 카테고리당 10개 샘플
            "rate_limit_delay": 0
        }
        
        try:
            # 벤치마크 실행
            report_path = run_benchmark(config)
            
            model_elapsed = time.time() - model_start
            results_summary.append({
                "model": model_name,
                "status": "✅ 완료",
                "time": model_elapsed,
                "report": report_path
            })
            
            print(f"\n✅ {model_name} 완료 (소요 시간: {model_elapsed:.1f}초)")
            
            # 다음 모델 실행 전 대기 (마지막 모델은 제외)
            if model_idx < len(MODELS_TO_TEST):
                wait_time = 10
                print(f"⏳ 다음 모델 실행 전 {wait_time}초 대기 중...")
                time.sleep(wait_time)
                
        except Exception as e:
            model_elapsed = time.time() - model_start
            error_msg = str(e)[:100]
            results_summary.append({
                "model": model_name,
                "status": f"❌ 실패: {error_msg}",
                "time": model_elapsed,
                "report": None
            })
            print(f"\n❌ {model_name} 실패: {error_msg}")
            print("다음 모델로 계속 진행합니다...")
            continue
    
    # 최종 결과 요약
    total_elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print("🎉 전체 벤치마크 완료!")
    print("=" * 80)
    print(f"⏱️  총 소요 시간: {total_elapsed / 60:.1f}분 ({total_elapsed:.1f}초)")
    print("\n📊 결과 요약:")
    print("-" * 80)
    
    for idx, result in enumerate(results_summary, 1):
        print(f"\n{idx}. {result['model']}")
        print(f"   상태: {result['status']}")
        print(f"   시간: {result['time']:.1f}초")
        if result['report']:
            print(f"   리포트: {result['report']}")
    
    print("\n" + "=" * 80)
    
    # 성공/실패 통계
    success_count = sum(1 for r in results_summary if "완료" in r['status'])
    fail_count = len(results_summary) - success_count
    
    print(f"✅ 성공: {success_count}/{len(MODELS_TO_TEST)}개")
    print(f"❌ 실패: {fail_count}/{len(MODELS_TO_TEST)}개")
    print(f"📁 결과 저장 위치: results/")
    print("=" * 80)

if __name__ == "__main__":
    run_multi_model_benchmark()
