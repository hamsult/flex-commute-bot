"""
Slack DM 기반 메시지 커스터마이징 핸들러.

- SocketMode로 봇 DM 이벤트 수신 (외부 URL/포트 불필요)
- 직원이 봇에게 DM으로 명령어를 보내면 커스텀 포맷 저장
- 설정은 data/user_formats.json에 영속 저장
"""

import logging
import os
import sys
from datetime import datetime

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(__file__))
from format_store import FormatStore, STATUS_KEYWORDS

HELP_TEXT = """*출퇴근 메시지 커스터마이징 봇* 사용법

*설정:*
`set 출근 🚀 {name} 출근이요! ({time})`
`set 퇴근 {name} 퇴근합니다 🌙 ({time})`
`set 휴게시작 ☕ {name} 잠깐 쉬어요`
`set 휴게종료 ⌨️ {name} 복귀! ({time})`

*조회/관리:*
`list` — 내 설정 전체 보기
`preview 출근` — 실제 메시지 미리보기
`clear 출근` — 출근 메시지 기본값으로 초기화
`clearall` — 전체 기본값으로 초기화

*사용 가능한 변수:*
`{name}` — 이름, `{time}` — 시간(HH:MM), `{status}` — 근태 상태

*지원 상태:* 출근, 퇴근, 휴게시작, 휴게종료"""


def _get_slack_name(client, user_id: str) -> str:
    """Slack users.info에서 real_name 조회"""
    try:
        res = client.users_info(user=user_id)
        profile = res["user"]["profile"]
        return profile.get("real_name") or profile.get("display_name") or user_id
    except Exception as e:
        logger.warning(f"users.info 조회 실패 ({user_id}): {e}")
        return user_id


def _load_default_format() -> str:
    import yaml
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)["slack"]["message_format"]


def _handle_message(body: dict, say, client) -> None:
    """DM 메시지 파싱 및 명령어 처리"""
    event = body.get("event", {})

    # 봇 자신의 메시지 무시
    if event.get("bot_id") or event.get("subtype"):
        return

    user_id = event.get("user", "")
    text = (event.get("text") or "").strip()
    channel = event.get("channel", "")

    if not user_id or not text:
        return

    store = FormatStore()
    parts = text.split(None, 2)  # 최대 3토큰으로 분리
    cmd = parts[0].lower() if parts else ""

    # help
    if cmd == "help" or cmd == "도움말":
        say(text=HELP_TEXT, channel=channel)
        return

    # list
    if cmd == "list":
        formats = store.get_all_formats(user_id)
        if not formats:
            say(text="설정된 커스텀 메시지가 없습니다.\n`help`를 입력하면 사용법을 볼 수 있어요.", channel=channel)
        else:
            lines = ["*내 커스텀 메시지 설정:*"]
            for kw, fmt in formats.items():
                lines.append(f"• *{kw}*: `{fmt}`")
            say(text="\n".join(lines), channel=channel)
        return

    # preview <상태>
    if cmd == "preview" and len(parts) >= 2:
        keyword = parts[1]
        if keyword not in STATUS_KEYWORDS:
            say(text=f"지원하지 않는 상태예요. 가능한 상태: {', '.join(STATUS_KEYWORDS)}", channel=channel)
            return

        slack_name = _get_slack_name(client, user_id)
        employee_id = store.resolve_employee_id(user_id, slack_name)
        now_str = datetime.now().strftime("%H:%M")

        formats = store.get_all_formats(user_id)
        fmt = formats.get(keyword)
        if fmt:
            try:
                preview = fmt.format(name=slack_name, status=keyword, time=now_str)
            except KeyError:
                preview = fmt
            say(text=f"*미리보기:*\n{preview}", channel=channel)
        else:
            default_fmt = _load_default_format()
            preview = default_fmt.format(name=slack_name, status=keyword, time=now_str)
            say(text=f"*미리보기 (기본 메시지):*\n{preview}", channel=channel)
        return

    # clear <상태>
    if cmd == "clear" and len(parts) >= 2:
        keyword = parts[1]
        if keyword not in STATUS_KEYWORDS:
            say(text=f"지원하지 않는 상태예요. 가능한 상태: {', '.join(STATUS_KEYWORDS)}", channel=channel)
            return
        if store.clear_format(user_id, keyword):
            say(text=f"*{keyword}* 메시지를 기본값으로 초기화했습니다.", channel=channel)
        else:
            say(text=f"*{keyword}* 메시지 설정이 없어요.", channel=channel)
        return

    # clearall
    if cmd == "clearall":
        store.clear_all(user_id)
        say(text="전체 커스텀 메시지를 기본값으로 초기화했습니다.", channel=channel)
        return

    # set <상태> <포맷>
    if cmd == "set" and len(parts) >= 3:
        keyword = parts[1]
        fmt = parts[2]

        if keyword not in STATUS_KEYWORDS:
            say(text=f"지원하지 않는 상태예요. 가능한 상태: {', '.join(STATUS_KEYWORDS)}", channel=channel)
            return

        # 직원 매핑
        slack_name = _get_slack_name(client, user_id)
        employee_id = store.resolve_employee_id(user_id, slack_name)

        if not employee_id:
            say(
                text=(
                    f"Flex에서 *{slack_name}* 이름의 직원을 찾지 못했어요.\n"
                    "Flex 등록 이름과 Slack 이름이 다른 경우 관리자에게 문의해주세요."
                ),
                channel=channel,
            )
            return

        store.set_format(user_id, employee_id, slack_name, keyword, fmt)

        # 미리보기
        now_str = datetime.now().strftime("%H:%M")
        try:
            preview = fmt.format(name=slack_name, status=keyword, time=now_str)
        except KeyError:
            preview = fmt

        say(
            text=f"✅ *{keyword}* 메시지가 저장됐습니다!\n미리보기: {preview}",
            channel=channel,
        )
        return

    # 알 수 없는 명령어
    say(text="`help`를 입력하면 사용법을 볼 수 있어요.", channel=channel)


async def start_socket_mode(bot_token: str, app_token: str) -> None:
    """SocketMode로 Slack 이벤트 수신 시작. main.py에서 asyncio.create_task()로 실행."""
    try:
        from slack_bolt.async_app import AsyncApp
        from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
    except ImportError:
        logger.error("slack-bolt가 설치되지 않았습니다. pip install slack-bolt 실행 후 재시작하세요.")
        return

    app = AsyncApp(token=bot_token)

    @app.event("message")
    async def handle_dm(body, say, client):
        event = body.get("event", {})
        # DM 채널만 처리 (channel_type == "im")
        if event.get("channel_type") != "im":
            return
        _handle_message(body, say, client)

    handler = AsyncSocketModeHandler(app, app_token)
    logger.info("Slack DM 핸들러 시작 (SocketMode)")
    await handler.start_async()
