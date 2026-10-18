from datetime import datetime

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


def start_system():
    print("=" * 45)
    print(PROJECT_NAME)
    print("=" * 45)

    print("시스템 시작 시간:", datetime.now())

    print("\nAI TEAM INITIALIZED\n")

    for name, role in AI_TEAM.items():
        print(f"{name} : {role}")

    print("\nSYSTEM STATUS: READY")
    print("TRADING MODE: PAPER ONLY")


if __name__ == "__main__":
    start_system()
