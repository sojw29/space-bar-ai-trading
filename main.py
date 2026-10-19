from datetime import datetime, timezone
import subprocess
import sys

PROJECT_NAME = "SPACE BAR AI TRADING"

AI_TEAM = {
    "COMMANDER": "전체 시스템 관리",
    "ATLAS": "시장 데이터 분석",
    "ORACLE": "시장 패턴 연구",
    "QUANT": "매매 전략 개발",
    "SCALPER": "초단타 전략 연구",
    "TESTER": "백테스트",
    "GUARDIAN": "리스크 관리",
    "EXECUTOR": "모의매매 실행",
    "EVOLVE": "AI 모델 학습",
    "AUDITOR": "성과 분석"
}


def run_agent(name, script):
    print(f"\n[COMMANDER] Starting {name}", flush=True)

    result = subprocess.run(
        [sys.executable, script],
        check=False
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{name} failed with code {result.returncode}"
        )

    print(f"[COMMANDER] {name} completed", flush=True)


def start_system():

    print("=" * 50)
    print(PROJECT_NAME)
    print("=" * 50)

    print(
        "Start time:",
        datetime.now(timezone.utc).isoformat()
    )

    print("\nAI TEAM INITIALIZED")

    for name, role in AI_TEAM.items():
        print(f"{name}: {role}")

    print("\nTRADING MODE: PAPER ONLY")
    print("LIVE TRADING: DISABLED")

    # STEP 1: Historical data collection
    run_agent(
        "HISTORY",
        "agents/history.py"
    )

    # STEP 2: Backtesting
    run_agent(
        "TESTER",
        "agents/tester.py"
    )

    print("\n" + "=" * 50)
    print("SYSTEM EXECUTION COMPLETED")
    print("=" * 50)


if __name__ == "__main__":
    try:
        start_system()
    except Exception as error:
        print(f"\nSYSTEM FAILED: {error}", flush=True)
        sys.exit(1)
