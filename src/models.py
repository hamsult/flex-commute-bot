from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AttendanceRecord(BaseModel):
    employee_id: str
    name: str
    status: str  # 코어출근, 자율출근, 코어퇴근, 자율퇴근, 휴게시작, 휴게종료 등
    timestamp: datetime
    raw: dict = {}


class AttendanceSnapshot(BaseModel):
    captured_at: datetime
    records: dict[str, AttendanceRecord]  # employee_id -> record


class AttendanceChange(BaseModel):
    employee: AttendanceRecord
    previous_status: Optional[str] = None
    new_status: str
