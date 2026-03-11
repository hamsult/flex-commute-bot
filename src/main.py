"""
Flex 근태 모니터링 메인 스케줄러.

- APScheduler로 07:00~22:00 KST, 1분 간격 폴링
- 연속 실패 감지 및 에러 처리
- 세션 만료 시 Slack 알림 후 종료
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Windows 터미널 UTF-8 출력 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Monitor:
    def __init__(self, scheduler) -> None:
        from crawler import FlexCrawler, SessionExpiredError, CrawlerError
        from state_manager import StateManager
        from notifier import SlackNotifier

        self.config = _load_config()
        self.mon_config = self.config["monitoring"]

        self.crawler = FlexCrawler()
        self.state_manager = StateManager()
        self.notifier = SlackNotifier()
        self.scheduler = scheduler

        self.consecutive_failures = 0

        self._SessionExpiredError = SessionExpiredError
        self._CrawlerError = CrawlerError

    async def run_cycle(self) -> None:
        retry_config = self.mon_config["retry"]
        backoff = retry_config["backoff_seconds"]
        max_attempts = retry_config["max_attempts"]

        for attempt in range(max_attempts):
            try:
                snapshot = await self.crawler.fetch_attendance()
                previous = self.state_manager.load_previous()
                changes = self.state_manager.detect_changes(previous, snapshot)

                for change in changes:
                    try:
                        self.notifier.notify_change(change)
                    except Exception as e:
                        logger.error(f"Slack 전송 실패: {e}")

                self.state_manager.save_current(snapshot)
                self.consecutive_failures = 0
                logger.info(f"모니터링 완료 — {len(snapshot.records)}명, 변경 {len(changes)}건")
                return

            except self._SessionExpiredError as e:
                logger.error(f"세션 만료: {e}")
                self.notifier.notify_session_expired()
                self.scheduler.shutdown(wait=False)
                return

            except Exception as e:
                logger.warning(f"크롤링 실패 (시도 {attempt + 1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
                    wait = backoff[attempt] if attempt < len(backoff) else backoff[-1]
                    logger.info(f"{wait}초 후 재시도...")
                    await asyncio.sleep(wait)

        # 모든 재시도 실패
        self.consecutive_failures += 1
        logger.error(f"연속 {self.consecutive_failures}회 실패")

        threshold = self.mon_config["consecutive_failure_threshold"]
        if self.consecutive_failures >= threshold:
            try:
                self.notifier.notify_error(
                    Exception(f"연속 {self.consecutive_failures}회 크롤링 실패"),
                    self.consecutive_failures,
                )
            except Exception:
                pass


scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
monitor: Monitor


async def job() -> None:
    await monitor.run_cycle()


async def reset_daily_state() -> None:
    """매일 06:00 KST 상태 초기화 — 전날 근태 상태가 잔류하지 않도록"""
    monitor.state_manager.reset()
    logger.info("일일 상태 초기화 완료")


async def check_session_age() -> None:
    """매일 09:00 KST 세션 파일 나이 확인 — 만료 임박 시 Slack 경고"""
    session_path = os.path.join(os.path.dirname(__file__), "..", "auth", "session.json")
    if not os.path.exists(session_path):
        return

    import time
    SESSION_EXPIRE_DAYS = 28  # 세션 유효기간 (일)
    WARN_DAYS_BEFORE = 7      # 만료 며칠 전부터 경고

    age_seconds = time.time() - os.path.getmtime(session_path)
    days_old = int(age_seconds / 86400)
    days_left = SESSION_EXPIRE_DAYS - days_old

    if days_left <= WARN_DAYS_BEFORE:
        logger.warning(f"세션 만료 임박: {days_old}일 경과, 약 {max(days_left, 0)}일 남음")
        monitor.notifier.notify_session_expiring_soon(days_old, max(days_left, 0))
    else:
        logger.info(f"세션 상태 양호: {days_old}일 경과, 약 {days_left}일 남음")


def main() -> None:
    global monitor, scheduler

    config = _load_config()
    mon_config = config["monitoring"]

    # 필수 환경변수 확인
    if not os.environ.get("SLACK_BOT_TOKEN"):
        logger.error("SLACK_BOT_TOKEN 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
        sys.exit(1)

    # session.json 존재 확인
    session_path = os.path.join(os.path.dirname(__file__), "..", "auth", "session.json")
    if not os.path.exists(session_path):
        logger.error("auth/session.json 파일이 없습니다. python src/auth_setup.py를 먼저 실행하세요.")
        sys.exit(1)

    interval = mon_config["poll_interval_minutes"]

    logger.info("Flex 근태 모니터링 시작")
    logger.info(f"폴링 간격: {interval}분 (24시간)")

    monitor = Monitor(scheduler)

    scheduler.add_job(
        job,
        trigger="cron",
        hour="*",
        minute=f"*/{interval}",
        id="flex_monitor",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        reset_daily_state,
        trigger="cron",
        hour=6,
        minute=0,
        id="daily_state_reset",
    )

    scheduler.add_job(
        check_session_age,
        trigger="cron",
        hour=9,
        minute=0,
        id="session_age_check",
    )

    asyncio.run(_run())


async def _run() -> None:
    scheduler.start()
    logger.info("스케줄러 실행 중... (Ctrl+C로 종료)")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        logger.info("종료 중...")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
