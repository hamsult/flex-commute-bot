"""
직원별 커스텀 메시지 포맷 저장소.

- data/user_formats.json에 Slack user_id 기준으로 저장
- get_format(): employee_id + status로 커스텀 포맷 조회
- set_format(): 저장, clear_format(): 특정 상태 초기화, clear_all(): 전체 초기화
- resolve_employee_id(): Slack 이름으로 state.json에서 employee_id 탐색
"""

import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Flex status 포함 관계 매핑: DM 명령어 키워드 → Flex status에 포함되는 문자열
STATUS_KEYWORDS = ["출근", "퇴근", "휴게시작", "휴게종료"]


def _data_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "data")


def _formats_path() -> str:
    return os.path.join(_data_dir(), "user_formats.json")


def _state_path() -> str:
    return os.path.join(_data_dir(), "state.json")


def _load_formats() -> dict:
    path = _formats_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_formats(data: dict) -> None:
    """원자적 저장: tmp 파일에 쓴 후 rename"""
    path = _formats_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dir_ = os.path.dirname(path)
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, encoding="utf-8", suffix=".tmp") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path = f.name
    os.replace(tmp_path, path)


def _match_keyword(status: str) -> Optional[str]:
    """Flex status 문자열에서 매칭되는 키워드 반환. 예: '코어출근' → '출근'"""
    for kw in STATUS_KEYWORDS:
        if kw in status:
            return kw
    return None


class FormatStore:
    def get_format(self, employee_id: str, status: str) -> Optional[str]:
        """
        employee_id와 Flex status로 커스텀 포맷 조회.
        '코어출근', '자율출근' 등은 모두 '출근' 키워드로 매칭.
        없으면 None 반환 (기본 포맷 폴백).
        """
        keyword = _match_keyword(status)
        if not keyword:
            return None

        data = _load_formats()
        for user_data in data.values():
            if user_data.get("employee_id") == employee_id:
                return user_data.get("formats", {}).get(keyword)
        return None

    def set_format(
        self,
        slack_user_id: str,
        employee_id: str,
        slack_name: str,
        status_key: str,
        fmt: str,
    ) -> None:
        """커스텀 포맷 저장"""
        data = _load_formats()
        if slack_user_id not in data:
            data[slack_user_id] = {
                "employee_id": employee_id,
                "slack_name": slack_name,
                "formats": {},
                "updated_at": "",
            }
        data[slack_user_id]["formats"][status_key] = fmt
        data[slack_user_id]["updated_at"] = datetime.now().isoformat(timespec="seconds")
        # employee_id/slack_name 항상 최신으로 갱신
        data[slack_user_id]["employee_id"] = employee_id
        data[slack_user_id]["slack_name"] = slack_name
        _save_formats(data)

    def clear_format(self, slack_user_id: str, status_key: str) -> bool:
        """특정 상태 포맷 삭제. 삭제 성공 시 True"""
        data = _load_formats()
        if slack_user_id not in data:
            return False
        formats = data[slack_user_id].get("formats", {})
        if status_key not in formats:
            return False
        del formats[status_key]
        data[slack_user_id]["updated_at"] = datetime.now().isoformat(timespec="seconds")
        _save_formats(data)
        return True

    def clear_all(self, slack_user_id: str) -> bool:
        """전체 포맷 초기화. 성공 시 True"""
        data = _load_formats()
        if slack_user_id not in data:
            return False
        data[slack_user_id]["formats"] = {}
        data[slack_user_id]["updated_at"] = datetime.now().isoformat(timespec="seconds")
        _save_formats(data)
        return True

    def get_all_formats(self, slack_user_id: str) -> dict:
        """해당 사용자의 포맷 딕셔너리 반환. 없으면 {}"""
        data = _load_formats()
        return data.get(slack_user_id, {}).get("formats", {})

    def get_user_entry(self, slack_user_id: str) -> Optional[dict]:
        """사용자 전체 데이터 반환"""
        data = _load_formats()
        return data.get(slack_user_id)

    def resolve_employee_id(self, slack_user_id: str, slack_name: str) -> Optional[str]:
        """
        1순위: user_formats.json에 이미 매핑된 employee_id 반환
        2순위: state.json에서 이름 일치하는 employee_id 탐색
        없으면 None
        """
        # 이미 매핑된 경우
        data = _load_formats()
        if slack_user_id in data and data[slack_user_id].get("employee_id"):
            return data[slack_user_id]["employee_id"]

        # state.json에서 이름으로 탐색
        state_path = _state_path()
        if not os.path.exists(state_path):
            return None
        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
            for emp_id, record in state.get("records", {}).items():
                if record.get("name") == slack_name:
                    return emp_id
        except (json.JSONDecodeError, OSError):
            pass
        return None


if __name__ == "__main__":
    # 단독 테스트
    store = FormatStore()
    print("=== FormatStore 단독 테스트 ===")

    store.set_format("U_TEST", "EMP_001", "테스트유저", "출근", "🚀 {name} 출근이요! ({time})")
    store.set_format("U_TEST", "EMP_001", "테스트유저", "퇴근", "{name} 퇴근합니다 🌙")

    print("get_format('EMP_001', '코어출근'):", store.get_format("EMP_001", "코어출근"))
    print("get_format('EMP_001', '자율퇴근'):", store.get_format("EMP_001", "자율퇴근"))
    print("get_format('EMP_001', '코어타임 휴게시작'):", store.get_format("EMP_001", "코어타임 휴게시작"))
    print("get_all_formats('U_TEST'):", store.get_all_formats("U_TEST"))

    store.clear_format("U_TEST", "출근")
    print("clear 출근 후 get_format:", store.get_format("EMP_001", "코어출근"))

    store.clear_all("U_TEST")
    print("clear_all 후 formats:", store.get_all_formats("U_TEST"))
    print("=== 테스트 완료 ===")
