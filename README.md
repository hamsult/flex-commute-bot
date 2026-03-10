# Flex Slack Monitor

Flex HR 시스템의 출퇴근 상태를 실시간으로 모니터링해 Slack에 자동 알림을 전송하는 봇입니다.

## 작동 방식

1. **Playwright** 브라우저가 1분마다 Flex 페이지에 접속
2. Flex 백엔드 API 응답을 가로채 전 직원 출퇴근 상태 파싱
3. 상태 변경이 감지되면 Slack `#commute` 채널에 메시지 전송
4. 에러/세션 만료 시 `#hr-monitor-alerts` 채널에 운영자 알림

```
코어타임 출근 → Slack: "홍길동님 코어타임 출근, 09:02"
자율 퇴근    → Slack: "김영희님 자율 퇴근, 18:31"
```

---

## 사전 준비

### 1. Slack Bot 생성

1. https://api.slack.com/apps 접속 → **Create New App** → From scratch
2. **OAuth & Permissions** → Bot Token Scopes에 추가:
   - `chat:write`
   - `chat:write.public`
3. **Install to Workspace** → Bot User OAuth Token (`xoxb-...`) 복사
4. `#commute`, `#hr-monitor-alerts` 채널에 봇 초대: `/invite @봇이름`

### 2. 환경 요구 사항

- Docker & Docker Compose
- Python 3.12+ (로컬에서 `auth_setup.py` 실행 시)
- 로컬 머신에서 Flex 접근 가능한 계정 (최초 1회)

---

## 설치 및 실행

### Step 1 — 코드 준비

```bash
git clone <repo-url>
cd flex-slack-monitor
```

### Step 2 — 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 SLACK_BOT_TOKEN 값 입력
```

### Step 3 — Flex 세션 초기화 (로컬에서 1회)

```bash
pip install playwright
playwright install chromium
python src/auth_setup.py
```

브라우저가 열리면 **Google 계정으로 Flex 로그인** 후 터미널에서 Enter.
`auth/session.json` 파일이 생성됩니다.

### Step 4 — 서버에 세션 파일 전송 (클라우드 배포 시)

```bash
scp auth/session.json user@서버주소:/앱경로/auth/session.json
```

### Step 5 — Docker로 실행

```bash
docker compose up -d
```

---

## 운영 가이드

### 로그 확인

```bash
docker compose logs -f
```

### 정상 작동 확인

```
2026-01-01 09:01:00 [INFO] Flex 근태 모니터링 시작
2026-01-01 09:01:00 [INFO] 활성 시간: 7:00 ~ 22:00 KST
2026-01-01 09:02:00 [INFO] 15명 데이터 파싱 완료
2026-01-01 09:02:00 [INFO] 모니터링 완료 — 15명, 변경 1건
```

### 세션 만료 시 대응

`#hr-monitor-alerts` 채널에 세션 만료 알림이 오면:

```bash
# 1. 로컬에서 세션 재생성
python src/auth_setup.py

# 2. 서버로 전송
scp auth/session.json user@서버주소:/앱경로/auth/session.json

# 3. 컨테이너 재시작
docker compose restart
```

> 세션 유효기간: 보통 7~30일 (Google SSO 정책에 따라 다름)

### 컨테이너 중지/재시작

```bash
docker compose stop      # 중지
docker compose start     # 재시작
docker compose restart   # 재시작 (설정 변경 시)
docker compose down      # 완전 종료
```

---

## 설정 파일

`config/config.yaml`에서 동작을 조정할 수 있습니다.

```yaml
monitoring:
  poll_interval_minutes: 1    # 폴링 간격 (분)
  active_hours:
    start: 7                  # 모니터링 시작 시간 (07:00 KST)
    end: 22                   # 모니터링 종료 시간 (22:00 KST)

slack:
  notify_channel: commute           # 출퇴근 알림 채널
  alert_channel: hr-monitor-alerts  # 운영자 알림 채널
  message_format: "{name}님 {status}, {time}"
```

---

## 알림 채널 구조

| 채널 | 알림 종류 |
|------|-----------|
| `#commute` | 직원 출근/퇴근/휴게 상태 변경 |
| `#hr-monitor-alerts` | 세션 만료, 연속 크롤링 실패 등 운영 이슈 |

---

## 파일 구조

```
flex-slack-monitor/
├── src/
│   ├── main.py          # 메인 스케줄러 (1분 폴링)
│   ├── crawler.py       # Playwright 기반 Flex 크롤러
│   ├── notifier.py      # Slack 알림 전송
│   ├── state_manager.py # 출퇴근 상태 저장/비교
│   ├── models.py        # 데이터 모델
│   └── auth_setup.py    # 최초 로그인 세션 생성 (로컬 1회)
├── config/
│   └── config.yaml      # 설정 파일
├── auth/
│   └── session.json     # Flex 로그인 세션 (gitignore)
├── data/
│   └── state.json       # 직전 근태 상태 (자동 관리)
├── .env                 # 환경변수 (gitignore)
├── .env.example         # 환경변수 예시
├── Dockerfile
└── docker-compose.yml
```

---

## 문제 해결

### 근태 데이터가 파싱되지 않을 때

```bash
# 디버그 데이터 확인
cat data/debug_api_response.json
```

API 응답이 비어있으면 세션 만료 가능성이 높습니다 → 세션 재생성 절차 진행.

### 컨테이너가 즉시 종료될 때

```bash
docker compose logs --tail=50
```

- `SLACK_BOT_TOKEN 환경변수가 설정되지 않았습니다` → `.env` 파일 확인
- `auth/session.json 파일이 없습니다` → `auth_setup.py` 재실행
