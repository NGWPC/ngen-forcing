"""Classes to enable status reporting through log calls with sentinel strings and JSON payloads."""

import re
from enum import StrEnum
from typing import Any

import ewts
from pydantic import BaseModel, ConfigDict, Field, validate_call

MSG_PAYLOAD_SENTINEL_START = "<MSG_DATA>"
MSG_PAYLOAD_SENTINEL_END = "</MSG_DATA>"
EXTRACT_PATTERN = re.compile(
    rf"{MSG_PAYLOAD_SENTINEL_START}(.*?){MSG_PAYLOAD_SENTINEL_END}"
)


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

    @property
    def json(self) -> str:
        """A json string (dict) representation for logging."""
        return self.model_dump_json()

    @property
    def json_wrapped(self) -> str:
        """A json string (dict) representation for logging, wrapped with sentinel strings."""
        return f"{MSG_PAYLOAD_SENTINEL_START}{self.json}{MSG_PAYLOAD_SENTINEL_END}"


def extract_payload_from_log_msg(log_msg: str) -> Payload | None:
    """Extract a Payload object from a log message, if it contains the sentinel. Otherwise, return None.
    Requires that the provided string is one line (Payloads should have escape newline chars via Pydantic model_dump_json()).

    Parameters
    ----------
    log_msg : str
        The log message to extract the payload from.

    Returns
    -------
    Payload | None
        The extracted Payload object if sentinel wrapping found, else None.

    Raises
    ----------
    ValueError
        If the log message contains a sentinel string wrapping but the content between cannot be parsed into a Payload instance.
        If the log message contains multiple sentinel string wrappings.
    """
    matches = EXTRACT_PATTERN.findall(log_msg)
    if matches:
        if len(matches) != 1:
            raise ValueError(
                f"{len(matches)} payloads detected in log message. Expected 1. Full message: {log_msg}"
            )
        payload_raw_str = matches[0]
        try:
            payload = Payload.model_validate_json(payload_raw_str)
        except Exception as e:
            raise ValueError(
                f"Payload was detected in log message, but failed to parse as JSON into a Payload instance. Full message: {repr(log_msg)}. Payload raw string: {repr(payload_raw_str)}. Exception: {e}"
            ) from e
        return payload
    else:
        return None


class LoggerWithPayload:
    """Wrapper around ewts.logger.EwtsLogger to enable injection of JSON payload into messages.

    Usage example:
        LOG = LoggerWithPayload(ewts.get_logger(ewts.FORCING_ID))
        LOG.info("This is the part of the msg not inside the payload", pld=Payload(Status.INPROG, 0.20, "Optional payload msg"))
    """

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
            msg = f"{msg}{pld.json_wrapped}"
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
