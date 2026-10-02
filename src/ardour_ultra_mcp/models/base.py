from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue

ObjectId = Annotated[str, Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.:-]+$")]
Name = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[^\x00-\x1f/\\]+$")]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Samples = Annotated[int, Field(strict=True, ge=0, le=9007199254740991)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ErrorCode(StrEnum):
    ARDOUR_NOT_CONNECTED = "ARDOUR_NOT_CONNECTED"
    SESSION_NOT_OPEN = "SESSION_NOT_OPEN"
    OBJECT_NOT_FOUND = "OBJECT_NOT_FOUND"
    STALE_OBJECT = "STALE_OBJECT"
    PLUGIN_NOT_FOUND = "PLUGIN_NOT_FOUND"
    PARAMETER_NOT_FOUND = "PARAMETER_NOT_FOUND"
    INVALID_TIME_POSITION = "INVALID_TIME_POSITION"
    BACKEND_UNSUPPORTED = "BACKEND_UNSUPPORTED"
    OPERATION_NOT_SUPPORTED = "OPERATION_NOT_SUPPORTED"
    IPC_TIMEOUT = "IPC_TIMEOUT"
    OSC_TIMEOUT = "OSC_TIMEOUT"
    BRIDGE_NOT_RUNNING = "BRIDGE_NOT_RUNNING"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFLICT = "CONFLICT"
    FILE_EXISTS = "FILE_EXISTS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    OUTCOME_UNCERTAIN = "OUTCOME_UNCERTAIN"
    BACKEND_ERROR = "BACKEND_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    BUSY = "BUSY"


class ErrorDetail(Model):
    code: ErrorCode
    message: str
    action: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


class DomainError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        action: str = "Refresh state and correct the request.",
        **details: JsonValue,
    ) -> None:
        super().__init__(message)
        self.detail = ErrorDetail(code=code, message=message, action=action, details=details)


class Options(Model):
    dry_run: bool = False
    expected_revision: str | None = Field(default=None, max_length=200)
    confirm_delete: bool = False


class Change(Model):
    object_id: str
    property: str
    before: JsonValue = None
    after: JsonValue = None


class Result(Model):
    success: bool = True
    data: dict[str, JsonValue] = Field(default_factory=dict)
    revision_before: str | None = None
    revision_after: str | None = None
    changed_objects: list[Change] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: ErrorDetail | None = None
