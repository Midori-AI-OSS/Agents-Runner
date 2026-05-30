"""Agents Runner Local Containerd GUI."""

from __future__ import annotations

import traceback
from typing import Any

from midori_ai_logger import MidoriAiLogger


def _format_standard_log_message(message: object, args: tuple[object, ...]) -> str:
    if not args:
        return str(message)
    try:
        return str(message) % args
    except Exception:
        extras = " ".join(str(arg) for arg in args)
        return f"{message} {extras}".strip()


def _format_standard_log_exc_info(exc_info: object) -> str:
    if not exc_info:
        return ""
    if exc_info is True:
        details = traceback.format_exc().strip()
        return "" if details == "NoneType: None" else details
    if isinstance(exc_info, BaseException):
        return "".join(traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__)).strip()
    if isinstance(exc_info, tuple) and len(exc_info) == 3:
        exc_type, exc, tb = exc_info
        return "".join(traceback.format_exception(exc_type, exc, tb)).strip()
    return ""


def _emit_standard_log(
    logger: MidoriAiLogger,
    *,
    mode: str,
    message: object,
    args: tuple[object, ...],
    exc_info: object = False,
    stack_info: bool = False,
) -> None:
    text = _format_standard_log_message(message, args)
    extras: list[str] = []
    exc_details = _format_standard_log_exc_info(exc_info)
    if exc_details:
        extras.append(exc_details)
    if stack_info:
        stack_details = "".join(traceback.format_stack()[:-1]).strip()
        if stack_details:
            extras.append(stack_details)
    if extras:
        text = "\n".join([text, *extras])
    logger.rprint(text, mode=mode)


def _install_midori_ai_logger_stdlib_compat() -> None:
    def debug(
        self: MidoriAiLogger,
        message: object,
        *args: object,
        exc_info: object = False,
        stack_info: bool = False,
        **_: Any,
    ) -> None:
        _emit_standard_log(
            self,
            mode="debug",
            message=message,
            args=args,
            exc_info=exc_info,
            stack_info=stack_info,
        )

    def info(
        self: MidoriAiLogger,
        message: object,
        *args: object,
        exc_info: object = False,
        stack_info: bool = False,
        **_: Any,
    ) -> None:
        _emit_standard_log(
            self,
            mode="normal",
            message=message,
            args=args,
            exc_info=exc_info,
            stack_info=stack_info,
        )

    def warning(
        self: MidoriAiLogger,
        message: object,
        *args: object,
        exc_info: object = False,
        stack_info: bool = False,
        **_: Any,
    ) -> None:
        _emit_standard_log(
            self,
            mode="warn",
            message=message,
            args=args,
            exc_info=exc_info,
            stack_info=stack_info,
        )

    def error(
        self: MidoriAiLogger,
        message: object,
        *args: object,
        exc_info: object = False,
        stack_info: bool = False,
        **_: Any,
    ) -> None:
        _emit_standard_log(
            self,
            mode="error",
            message=message,
            args=args,
            exc_info=exc_info,
            stack_info=stack_info,
        )

    def critical(
        self: MidoriAiLogger,
        message: object,
        *args: object,
        exc_info: object = False,
        stack_info: bool = False,
        **_: Any,
    ) -> None:
        _emit_standard_log(
            self,
            mode="error",
            message=message,
            args=args,
            exc_info=exc_info,
            stack_info=stack_info,
        )

    def exception(
        self: MidoriAiLogger,
        message: object,
        *args: object,
        exc_info: object = True,
        stack_info: bool = False,
        **_: Any,
    ) -> None:
        _emit_standard_log(
            self,
            mode="error",
            message=message,
            args=args,
            exc_info=exc_info,
            stack_info=stack_info,
        )

    for name, method in {
        "debug": debug,
        "info": info,
        "warning": warning,
        "warn": warning,
        "error": error,
        "critical": critical,
        "exception": exception,
    }.items():
        if not hasattr(MidoriAiLogger, name):
            setattr(MidoriAiLogger, name, method)


_install_midori_ai_logger_stdlib_compat()
