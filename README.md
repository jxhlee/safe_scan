---
title: 약관 세이프스캔
emoji: 📄
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# 약관 세이프스캔 (ToS Safe-Reading Engine)

이용약관·개인정보 처리방침에서 위험할 수 있는 조항을 자동으로 찾아 체크리스트·요약·강조 원문으로 보여주는 읽기 보조 도구입니다.

**법률 자문이 아닌 읽기 보조 및 체크리스트 도구입니다.** 최종 판단은 반드시 원문을 직접 확인하세요.

## 핵심 알고리즘

- **Aho-Corasick** (`pyahocorasick`) — 위험 신호 문구 수백 개를 문서 한 번 순회로 탐지
- **TextRank** (`networkx` PageRank) — 위험 조항에 가중치를 준 그래프 기반 추출 요약, Kiwi(`kiwipiepy`) 형태소 분석 기반 문장 유사도 사용

## 실행 방법

### 데스크톱 앱 (pywebview)

```bash
pip install -r requirements-desktop.txt
python main.py
```

### 웹 서버 (FastAPI)

```bash
pip install -r requirements-web.txt
uvicorn server:app --host 0.0.0.0 --port 7860
```

두 방식 모두 `app/core/` 아래의 동일한 분석 파이프라인과 `app/ui/web/` 프론트엔드를 공유합니다.

## 배포

**Render.com** (무료, 카드 등록 불필요)을 기준으로 합니다:

1. 이 저장소를 GitHub에 push
2. Render 대시보드 → New → Web Service → 이 GitHub 저장소 선택
3. Language를 **Docker**로 설정 (저장소 루트의 `Dockerfile` 자동 인식)
4. Instance Type을 **Free** 선택 후 Deploy

무료 인스턴스는 15분간 요청이 없으면 잠들고, 다음 요청 시 깨어나는 데 약 1분이 걸립니다.

(참고: Hugging Face Spaces의 Docker SDK는 Static과 달리 PRO 유료 요금제가 있어야 생성할 수 있어, 무료로는 사용할 수 없습니다.)
