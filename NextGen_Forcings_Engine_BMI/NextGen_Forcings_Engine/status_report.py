"""Classes to enable status reporting through log calls with sentinel strings and JSON payloads."""

from enum import StrEnum
from typing import Any

import ewts
from pydantic import BaseModel, ConfigDict, Field, validate_call

MSG_PAYLOAD_SENTINEL_START = "<MSG_DATA>"
MSG_PAYLOAD_SENTINEL_END = "</MSG_DATA>"


class Status(StrEnum):
    """Status enum for log JSON payload."""

    NULL = "NULL"
    INITTING = "INITIALIZING"
    INITTED = "INITIALIZED"
    STARTING = "STARTING"
    INPROG = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


class Payload(BaseModel):
    """Log pld class for status reporting via logs.
    __init__ is defined simply to allow positional arguments within Pydanic BaseModel framework."""

    status: Status = Field(description="Status")
    prog: float | None = Field(
        default=None, ge=0, le=1, description="Progress (0.0 to 1.0)"
    )
    msg: str | None = Field(default=None, description="Message")
    modnm: str | None = Field(
        default=None,
        description="Module name (LoggerWithPayload gleans this and overrides it)",
    )

    def __init__(
        self,
        status: Status,
        prog: float | None = None,
        msg: str | None = None,
        modnm: str | None = None,
    ):
        """__init__ is defined simply to allow positional arguments within Pydanic BaseModel framework."""
        super().__init__(status=status, prog=prog, msg=msg, modnm=modnm)


class LoggerWithPayload:
    """Wrapper around ewts.logger.EwtsLogger to enable injection of JSON payload into messages."""

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self, ewts_logger: ewts.logger.BoundEwtsLoggerProxy | ewts.logger.EwtsLogger
    ):
        self.logger = ewts_logger

    @validate_call
    def __msg_w_payload(self, msg: str | Any, pld: Payload | None) -> str | Any:
        """Overrides the modnm attribute based on the value from the existing EWTS logger (self.logger).
        Then builds and returns the message including the JSON pld and sentinel string."""
        if pld is not None:
            pld.modnm = self.logger.ewts_id
            msg = f"{msg}{MSG_PAYLOAD_SENTINEL_START}{pld.model_dump_json()}{MSG_PAYLOAD_SENTINEL_END}"
        return msg

    def debug(self, msg, *args, pld: Payload | None = None, **kwargs):
        self.logger.debug(self.__msg_w_payload(msg, pld), *args, **kwargs)

    def perform(self, msg, *args, pld: Payload | None = None, **kwargs):
        self.logger.perform(self.__msg_w_payload(msg, pld), *args, **kwargs)

    def info(self, msg, *args, pld: Payload | None = None, **kwargs):
        self.logger.info(self.__msg_w_payload(msg, pld), *args, **kwargs)

    def warning(self, msg, *args, pld: Payload | None = None, **kwargs):
        self.logger.warning(self.__msg_w_payload(msg, pld), *args, **kwargs)

    def severe(self, msg, *args, pld: Payload | None = None, **kwargs):
        self.logger.severe(self.__msg_w_payload(msg, pld), *args, **kwargs)

    def error(self, msg, *args, pld: Payload | None = None, **kwargs):
        self.logger.error(self.__msg_w_payload(msg, pld), *args, **kwargs)

    def fatal(self, msg, *args, pld: Payload | None = None, **kwargs):
        self.logger.fatal(self.__msg_w_payload(msg, pld), *args, **kwargs)

    def critical(self, msg, *args, pld: Payload | None = None, **kwargs):
        self.logger.critical(self.__msg_w_payload(msg, pld), *args, **kwargs)

    # def bind(self):
    #     return self.logger.bind()

    # So users can call other ewts methods, notably bind(), etc.
    def __getattr__(self, name):
        return getattr(self.logger, name)
