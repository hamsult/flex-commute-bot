"""
Slack Bot 알림 모듈.

- chat.postMessage로 #commute 채널에 출퇴근 알림 전송
- 에러/세션 만료 시 #hr-monitor-alerts 채널에 운영자 알림
"""

import argparse
import logging
import os
import sys
from datetime import datetime

import yaml

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(__file__))
from models import AttendanceChange


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class SlackNotifier:
    def __init__(self) -> None:
        self.token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not self.token:
            raise ValueError(
                "SLACK_BOT_TOKEN 환경변수가 설정되지 않았습니다.\n"
                ".env 파일에 SLACK_BOT_TOKEN=xoxb-... 를 추가하세요."
            )

        try:
            from slack_sdk import WebClient
        except ImportError:
            raise ImportError("slack_sdk가 설치되지 않았습니다. pip install slack-sdk")

        self.client = WebClient(token=self.token)
        config = _load_config()
        self.notify_channel = config["slack"]["notify_channel"]
        self.alert_channel = config["slack"]["alert_channel"]
        self.message_format = config["slack"]["message_format"]

        from format_store import FormatStore
        self.format_store = FormatStore()

    def _send(self, channel: str, text: str) -> None:
        try:
            self.client.chat_postMessage(channel=channel, text=text)
        except Exception as e:
            print(f"[Slack 전송 실패] 채널={channel}, 오류={e}")
            raise

    def notify_change(self, change: AttendanceChange) -> None:
        name = change.employee.name
        status = change.new_status
        time_str = change.employee.timestamp.strftime("%H:%M")

        # 점심 자동 휴게 필터링 (12:00~13:59 사이의 휴게시작/휴게종료는 알림 생략)
        if "휴게시작" in status or "휴게종료" in status:
            hour = change.employee.timestamp.hour
            if 12 <= hour <= 13:
                logger.info(f"점심 휴게 알림 생략: {name} {status} {time_str}")
                return

        custom_fmt = self.format_store.get_format(change.employee.employee_id, status)
        template = custom_fmt if custom_fmt else self.message_format
        try:
            message = template.format(name=name, status=status, time=time_str)
        except KeyError:
            message = self.message_format.format(name=name, status=status, time=time_str)
        self._send(self.notify_channel, message)
        print(f"[Slack 전송] {message}")

    def notify_session_expired(self) -> None:
        msg = (
            "[Flex 모니터] 세션이 만료되었습니다.\n"
            "로컬에서 `python src/auth_setup.py`를 실행한 뒤\n"
            "`auth/session.json`을 서버에 전송하고 컨테이너를 재시작하세요."
        )
        try:
            self._send(self.alert_channel, msg)
        except Exception as e:
            logger.error(f"세션 만료 알림 전송 실패. 수동으로 확인 필요: {e}")

    def notify_session_expiring_soon(self, days_old: int, days_left: int) -> None:
        msg = (
            f"[Flex 모니터] 세션 만료 임박 경고\n"
            f"마지막 로그인: {days_old}일 전\n"
            f"예상 만료까지: 약 {days_left}일\n"
            f"login.bat 을 실행해서 Flex 재로그인 해주세요."
        )
        try:
            self._send(self.alert_channel, msg)
        except Exception as e:
            logger.error(f"세션 만료 임박 알림 전송 실패: {e}")

    def notify_error(self, error: Exception, consecutive_count: int = 1) -> None:
        msg = (
            f"[Flex 모니터] 연속 {consecutive_count}회 오류 발생\n"
            f"오류 내용: {type(error).__name__}: {error}"
        )
        try:
            self._send(self.alert_channel, msg)
        except Exception as e:
            logger.error(f"에러 알림 Slack 전송 실패: {e}")

    def send_test_message(self) -> None:
        now = datetime.now().strftime("%H:%M")
        test_msg = self.message_format.format(name="테스트직원", status="코어출근", time=now)
        print(f"테스트 메시지를 #{self.notify_channel} 채널에 전송합니다...")
        self._send(self.notify_channel, f"[테스트] {test_msg}")
        print("전송 완료!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="테스트 메시지 전송")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    notifier = SlackNotifier()
    if args.test:
        notifier.send_test_message()
    else:
        print("--test 옵션을 사용하세요: python src/notifier.py --test")
