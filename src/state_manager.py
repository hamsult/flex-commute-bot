"""
근태 상태 저장 및 변경 감지 모듈.

- data/state.json에 직전 스냅샷 저장
- 최초 실행 시 스냅샷만 저장하고 알림 없음 (스팸 방지)
- 이후 실행 시 employee_id 기준 status 비교 -> 변경 시 AttendanceChange 반환
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from models import AttendanceChange, AttendanceRecord, AttendanceSnapshot


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _record_to_dict(record: AttendanceRecord) -> dict:
    return {
        "employee_id": record.employee_id,
        "name": record.name,
        "status": record.status,
        "timestamp": record.timestamp.isoformat(),
    }


def _record_from_dict(d: dict) -> AttendanceRecord:
    return AttendanceRecord(
        employee_id=d["employee_id"],
        name=d["name"],
        status=d["status"],
        timestamp=datetime.fromisoformat(d["timestamp"]),
        raw={},
    )


class StateManager:
    def __init__(self) -> None:
        config = _load_config()
        self.state_file = os.path.join(
            os.path.dirname(__file__), "..", config["state"]["file"]
        )
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

    def load_previous(self) -> Optional[AttendanceSnapshot]:
        if not os.path.exists(self.state_file):
            return None
        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            records = {
                emp_id: _record_from_dict(r)
                for emp_id, r in data.get("records", {}).items()
            }
            return AttendanceSnapshot(
                captured_at=datetime.fromisoformat(data["captured_at"]),
                records=records,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[상태 관리] 이전 상태 파일 읽기 실패 (무시): {e}")
            return None

    def save_current(self, snapshot: AttendanceSnapshot) -> None:
        data = {
            "captured_at": snapshot.captured_at.isoformat(),
            "records": {
                emp_id: _record_to_dict(r)
                for emp_id, r in snapshot.records.items()
            },
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def reset(self) -> None:
        """state.json 초기화 (매일 새벽 호출)"""
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        logger.info("state.json 초기화 완료")

    def detect_changes(
        self,
        previous: Optional[AttendanceSnapshot],
        current: AttendanceSnapshot,
    ) -> list[AttendanceChange]:
        """
        이전 스냅샷과 현재 스냅샷을 비교하여 변경된 항목을 반환합니다.
        최초 실행(previous=None)이면 빈 리스트 반환 (스팸 방지).
        status가 동일하고 timestamp 차이가 5분 이내이면 중복 이벤트로 간주해 제외.
        """
        if previous is None:
            logger.info("최초 실행 — 현재 상태를 기준으로 저장합니다. 알림 없음.")
            return []

        changes: list[AttendanceChange] = []

        for emp_id, current_record in current.records.items():
            prev_record = previous.records.get(emp_id)

            if prev_record is None:
                # 새로 등장한 직원 (신규 입사 또는 부서 이동)
                changes.append(
                    AttendanceChange(
                        employee=current_record,
                        previous_status=None,
                        new_status=current_record.status,
                    )
                )
            elif prev_record.status != current_record.status:
                # 상태 변경
                changes.append(
                    AttendanceChange(
                        employee=current_record,
                        previous_status=prev_record.status,
                        new_status=current_record.status,
                    )
                )
            else:
                # status 동일 — timestamp 차이가 5분 초과이면 새 이벤트로 간주 (중복 방지)
                try:
                    diff = abs((current_record.timestamp - prev_record.timestamp).total_seconds())
                    if diff > 360:
                        changes.append(
                            AttendanceChange(
                                employee=current_record,
                                previous_status=prev_record.status,
                                new_status=current_record.status,
                            )
                        )
                except TypeError:
                    # timezone-aware vs naive 혼용 시 비교 불가 → 알림 없음
                    pass

        return changes
