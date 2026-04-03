# ICOM Agent

KAIST CAIO - ICOM 데이터 연동 및 수요 예측 시스템

## 프로젝트 구조

```
icom-agent/
├── data_collector/     # 데이터 수집 모듈
├── demand_predictor/   # 수요 예측 모듈
├── optimizer/          # 최적화 모듈
├── simulator/          # 시뮬레이터
├── dashboard/          # Streamlit 대시보드
├── shared/             # 공통 유틸리티
├── tests/              # 테스트
└── models/             # 저장된 모델
```

## 설치

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

## 환경 설정

`.env.example`을 참고하여 `.env` 파일 생성

## 실행

```bash
# 대시보드 실행
streamlit run dashboard/app.py

# API 서버 실행 (Phase 1)
uvicorn api.main:app --reload
```

## 개발 단계

- **Phase 0**: 데이터 수집 및 EDA
- **Phase 1**: 수요 예측 모델 개발
- **Phase 2**: 최적화 및 시뮬레이션
- **Phase 3**: LLM 에이전트 통합

## 테스트

```bash
pytest tests/
```

## 라이선스

Private - KAIST CAIO
