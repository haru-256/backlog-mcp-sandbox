import json
from io import StringIO

import pytest
from loguru import logger
from pydantic import ValidationError

from chat.logging_config import configure_logging
from chat.request_context import request_id_var
from chat.settings import Settings


def test_configure_logging_human(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_FORMAT=human のとき configure_logging が human を返し、ログが出力できることを確かめる。"""
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "test-key")
    monkeypatch.setenv("LOG_FORMAT", "human")

    settings = Settings.from_env()
    assert configure_logging(settings) == "human"

    buffer = StringIO()
    logger.remove()
    logger.add(buffer, format="{message}")

    logger.bind(request_id="req-1").info("hello")
    assert "hello" in buffer.getvalue()


def test_configure_logging_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_FORMAT=json のとき structured ログに message と bind した request_id が載ることを確かめる。"""
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "test-key")
    monkeypatch.setenv("LOG_FORMAT", "json")

    settings = Settings.from_env()
    assert configure_logging(settings) == "json"

    buffer = StringIO()
    logger.remove()
    logger.add(buffer, serialize=True)

    logger.bind(request_id="req-2").info("structured")
    record = json.loads(buffer.getvalue().strip())
    assert record["record"]["message"] == "structured"
    assert record["record"]["extra"]["request_id"] == "req-2"


def test_patch_record_uses_contextvar_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """request_id_var を set したとき、bind なしの json ログに request_id が載ることを確かめる。

    HTTP middleware が contextvars に載せた ID が、agent など下流の logger 呼び出しにも
    patcher 経由で伝わる経路を検証する。
    """
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "test-key")
    monkeypatch.setenv("LOG_FORMAT", "json")

    settings = Settings.from_env()
    configure_logging(settings)

    buffer = StringIO()
    logger.remove()
    logger.add(buffer, serialize=True)

    token = request_id_var.set("ctx-req-1")
    try:
        logger.info("from context")
    finally:
        request_id_var.reset(token)

    record = json.loads(buffer.getvalue().strip())
    assert record["record"]["message"] == "from context"
    assert record["record"]["extra"]["request_id"] == "ctx-req-1"


def test_patch_record_uses_contextvar_human(monkeypatch: pytest.MonkeyPatch) -> None:
    """request_id_var を set したとき、human フォーマットの出力にも request_id が含まれることを確かめる。"""
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "test-key")
    monkeypatch.setenv("LOG_FORMAT", "human")

    settings = Settings.from_env()
    configure_logging(settings)

    buffer = StringIO()
    logger.remove()
    logger.add(buffer, format="{extra[request_id]}|{message}")

    token = request_id_var.set("ctx-req-2")
    try:
        logger.info("from context")
    finally:
        request_id_var.reset(token)

    assert buffer.getvalue() == "ctx-req-2|from context\n"


def test_patch_record_defaults_request_id_without_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """contextvars 未設定時（CLI など）に request_id がデフォルトの "-" になることを確かめる。"""
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "test-key")
    monkeypatch.setenv("LOG_FORMAT", "json")

    settings = Settings.from_env()
    configure_logging(settings)

    buffer = StringIO()
    logger.remove()
    logger.add(buffer, serialize=True)

    logger.info("no context")

    record = json.loads(buffer.getvalue().strip())
    assert record["record"]["extra"]["request_id"] == "-"


def test_settings_rejects_unknown_log_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_FORMAT に human/json 以外を指定したとき Settings の検証が失敗することを確かめる。"""
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "test-key")
    monkeypatch.setenv("LOG_FORMAT", "xml")

    with pytest.raises(ValidationError):
        Settings.from_env()
