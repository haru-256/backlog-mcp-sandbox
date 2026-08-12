from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
"""現在の HTTP リクエスト ID。未設定時は "-"。"""
