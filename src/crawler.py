"""
Playwright 기반 Flex 근태 크롤러.

전략:
1. 저장된 세션(auth/session.json)으로 Flex 페이지에 접근
2. page.on("response")로 백엔드 API 응답을 가로채 근태 데이터 추출
   - work-clock/users: 전체 직원 출퇴근 기록
   - department-users/search: 직원 이름 매핑
   - work-forms: 출근 유형(코어/자율 등) 매핑
3. 세션 만료 시 SessionExpiredError 발생
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from models import AttendanceRecord, AttendanceSnapshot


class SessionExpiredError(Exception):
    pass


class CrawlerError(Exception):
    pass


logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _ts_to_datetime(ts_ms: int) -> datetime:
    """Unix timestamp (ms) -> KST datetime (timezone-aware)"""
    return datetime.fromtimestamp(ts_ms / 1000, tz=_KST)


EVENT_TYPE_MAP = {
    "START": "출근",
    "STOP": "퇴근",
    "REST_START": "휴게시작",
    "REST_STOP": "휴게종료",
    "SWITCH": "근무전환",
}

# 근무 유형 이름 축약 규칙
WORK_FORM_SHORT = {
    "코어타임 근무": "코어타임",
    "자율근무(코어타임 외)": "자율",
    "재택 근무": "재택",
    "외근": "외근",
    "출장": "출장",
    "휴일, 야간 근무": "야간",
    "휴게": "",  # 휴게는 EVENT_TYPE_MAP으로 충분
}


def _shorten_work_form_name(name: str) -> str:
    """근무 유형 이름을 간결하게 축약. 매핑 없으면 원본 반환."""
    if not name:
        return ""
    return WORK_FORM_SHORT.get(name, name)


def _parse_work_clock_response(
    response_data: dict,
    name_map: dict[str, str],
    work_form_map: dict[str, str],
    prev_snapshot: Optional["AttendanceSnapshot"],
) -> dict[str, AttendanceRecord]:
    """
    work-clock/users API 응답에서 근태 레코드 파싱.
    가장 최신 이벤트를 현재 상태로 사용.
    """
    records: dict[str, AttendanceRecord] = {}

    for user_data in response_data.get("records", []):
        user_id = user_data.get("userIdHash", "")
        if not user_id:
            continue

        name = name_map.get(user_id, user_id)

        # 오늘 날짜 기록 찾기
        today_records = user_data.get("records", [])
        if not today_records:
            continue

        today = today_records[0]  # 오늘 날짜 데이터
        packs = today.get("workClockRecordPacks", [])
        if not packs:
            continue

        # 가장 최신 pack의 마지막 이벤트 추출
        latest_pack = packs[-1]
        last_event_type = None
        last_event_time = None
        last_work_form_id = None

        # startRecord의 근무 유형은 항상 기준으로 사용 (stopRecord에는 없을 수 있음)
        start_work_form_id = latest_pack.get("startRecord", {}).get("customerWorkFormId")

        # 진행 중인 pack 우선
        if latest_pack.get("onGoing"):
            rest_records = latest_pack.get("restRecords", [])
            if rest_records:
                last_rest = rest_records[-1]
                if last_rest.get("restStopRecord"):
                    last_event_type = "REST_STOP"
                    last_event_time = last_rest["restStopRecord"].get("targetTime")
                    last_work_form_id = last_rest["restStopRecord"].get("customerWorkFormId") or start_work_form_id
                elif last_rest.get("restStartRecord"):
                    last_event_type = "REST_START"
                    last_event_time = last_rest["restStartRecord"].get("targetTime")
                    last_work_form_id = last_rest["restStartRecord"].get("customerWorkFormId") or start_work_form_id
                else:
                    logger.warning(f"restRecords에 restStartRecord도 없음: {last_rest}")
                    continue
            else:
                last_event_type = "START"
                last_event_time = latest_pack["startRecord"].get("realTime") or latest_pack["startRecord"].get("targetTime")
                last_work_form_id = start_work_form_id
        else:
            # 종료된 pack: STOP이 마지막
            if latest_pack.get("stopRecord"):
                last_event_type = "STOP"
                last_event_time = latest_pack["stopRecord"].get("realTime") or latest_pack["stopRecord"].get("targetTime")
                # stopRecord에 customerWorkFormId 없으면 startRecord 유형 사용
                last_work_form_id = latest_pack["stopRecord"].get("customerWorkFormId") or start_work_form_id
            else:
                last_event_type = "START"
                last_event_time = latest_pack["startRecord"].get("realTime") or latest_pack["startRecord"].get("targetTime")
                last_work_form_id = start_work_form_id

        if not last_event_type or not last_event_time:
            continue

        # 출근 유형 매핑 (코어출근, 자율출근 등)
        work_form_name = work_form_map.get(str(last_work_form_id), "") if last_work_form_id else ""
        base_event = EVENT_TYPE_MAP.get(last_event_type, last_event_type)

        # 유형명 간결하게 축약
        short_name = _shorten_work_form_name(work_form_name)
        if short_name:
            status = f"{short_name} {base_event}"
        else:
            status = base_event

        timestamp = _ts_to_datetime(last_event_time)

        records[user_id] = AttendanceRecord(
            employee_id=user_id,
            name=name,
            status=status,
            timestamp=timestamp,
            raw=user_data,
        )

    return records


class FlexCrawler:
    def __init__(self) -> None:
        self.config = _load_config()
        self.flex_config = self.config["flex"]
        self.session_path = os.path.join(
            os.path.dirname(__file__), "..", self.flex_config["session_file"]
        )

    async def fetch_attendance(self, prev_snapshot: Optional[AttendanceSnapshot] = None) -> AttendanceSnapshot:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise CrawlerError("playwright가 설치되지 않았습니다.")

        if not os.path.exists(self.session_path):
            raise CrawlerError(
                f"세션 파일이 없습니다: {self.session_path}\n"
                "먼저 python3 src/auth_setup.py를 실행하세요."
            )

        captured: dict[str, list] = {
            "work_clock": [],
            "users": [],
            "work_forms": [],
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            try:
                context = await browser.new_context(
                    storage_state=self.session_path,
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                await context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
                page = await context.new_page()

                api_received = asyncio.Event()

                async def handle_response(response):
                    url = response.url
                    try:
                        ct = response.headers.get("content-type", "")
                        if "json" not in ct:
                            return
                        if "work-clock/users" in url and "current-status" not in url:
                            data = await response.json()
                            captured["work_clock"].append(data)
                            api_received.set()
                        elif "department-users/search" in url or "search-users" in url:
                            data = await response.json()
                            captured["users"].append(data)
                        elif "work-forms" in url and "time-off" not in url:
                            data = await response.json()
                            captured["work_forms"].append(data)
                    except Exception:
                        pass

                page.on("response", handle_response)

                try:
                    await page.goto(
                        self.flex_config["url"],
                        wait_until="load",
                        timeout=self.flex_config["page_load_timeout"],
                    )
                except Exception as e:
                    logger.warning(f"page.goto() 예외 (계속 진행): {type(e).__name__}: {e}")

                # work-clock API 응답이 올 때까지 최대 30초 대기
                try:
                    await asyncio.wait_for(api_received.wait(), timeout=30)
                    logger.info("work-clock API 응답 수신 완료")
                except asyncio.TimeoutError:
                    logger.warning("work-clock API 응답 대기 시간 초과 (30초)")

                # 나머지 API(users, work-forms)가 완료될 시간 추가 대기
                await page.wait_for_timeout(3000)

                if "login" in page.url or "accounts.google" in page.url:
                    raise SessionExpiredError("Flex 세션이 만료되었습니다.")

            finally:
                await browser.close()

        # 직원 이름 매핑 구성
        name_map = _build_name_map(captured["users"])

        # 근무 유형 매핑 구성 (work form id -> 유형명)
        work_form_map = _build_work_form_map(captured["work_forms"])

        # 근태 레코드 파싱
        records: dict[str, AttendanceRecord] = {}
        for wc_data in captured["work_clock"]:
            parsed = _parse_work_clock_response(wc_data, name_map, work_form_map, prev_snapshot)
            records.update(parsed)

        # 디버그 저장 (항상)
        debug_path = os.path.join(os.path.dirname(__file__), "..", "data", "debug_api_response.json")
        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(captured, f, ensure_ascii=False, indent=2, default=str)

        if not records:
            logger.warning("근태 데이터를 파싱하지 못했습니다. data/debug_api_response.json 확인")
        else:
            logger.info(f"{len(records)}명 데이터 파싱 완료")

        return AttendanceSnapshot(captured_at=datetime.now(tz=_KST), records=records)

    async def debug_api_urls(self) -> None:
        """개발용: Flex 페이지에서 호출되는 모든 API URL 출력"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            print("playwright가 설치되지 않았습니다.")
            return

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=self.session_path)
            page = await context.new_page()

            print("=== Flex 페이지 API 요청 목록 ===")

            async def log_response(response):
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    print(f"  {response.status} {response.url}")

            page.on("response", log_response)
            await page.goto(self.flex_config["url"], wait_until="load", timeout=60000)
            await page.wait_for_timeout(15000)
            print(f"  [현재 URL] {page.url}")
            await browser.close()
            print("=================================")


def _build_name_map(user_responses: list) -> dict[str, str]:
    """API 응답에서 userIdHash -> 이름 매핑 구성"""
    name_map: dict[str, str] = {}
    for resp in user_responses:
        items = []
        if isinstance(resp, list):
            items = resp
        elif isinstance(resp, dict):
            for key in ("content", "data", "items", "results", "members", "employees", "users"):
                if key in resp and isinstance(resp[key], list):
                    items = resp[key]
                    break

        for item in items:
            if not isinstance(item, dict):
                continue
            uid = item.get("userIdHash") or item.get("id") or item.get("userId")
            name = (
                item.get("name")
                or item.get("korName")
                or item.get("displayName")
                or item.get("fullName")
                or (item.get("user", {}) or {}).get("name")
            )
            if uid and name:
                name_map[str(uid)] = str(name)
    return name_map


def _build_work_form_map(work_form_responses: list) -> dict[str, str]:
    """
    work-forms API 응답에서 customerWorkFormId -> 유형명 매핑 구성.
    예: {"973573": "코어타임 근무", "979060": "자율 근무"}
    """
    wf_map: dict[str, str] = {}
    for resp in work_form_responses:
        items = []
        if isinstance(resp, list):
            items = resp
        elif isinstance(resp, dict):
            for key in ("workForms", "content", "data", "items", "forms"):
                if key in resp and isinstance(resp[key], list):
                    items = resp[key]
                    break

        for item in items:
            if not isinstance(item, dict):
                continue
            wf_id = str(
                item.get("customerWorkFormId")
                or item.get("id")
                or item.get("workFormId")
                or ""
            )
            # display.name 우선, 없으면 name
            display = item.get("display") or {}
            name = display.get("name") or item.get("name") or item.get("workFormName") or ""
            if wf_id and name:
                wf_map[wf_id] = str(name)
    return wf_map


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-urls", action="store_true")
    args = parser.parse_args()

    crawler = FlexCrawler()
    if args.debug_urls:
        asyncio.run(crawler.debug_api_urls())
    else:
        snapshot = asyncio.run(crawler.fetch_attendance())
        print(f"\n[결과] {len(snapshot.records)}명 ({snapshot.captured_at.strftime('%H:%M:%S')})")
        for emp_id, r in snapshot.records.items():
            print(f"  {r.name} ({emp_id}): {r.status} {r.timestamp.strftime('%H:%M')}")
