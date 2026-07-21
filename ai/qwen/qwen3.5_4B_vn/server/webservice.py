import json
import os
import signal
import threading
import time
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from websocket import WebSocketApp


SCRIPT_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, os.pardir, "config.json"))


def load_config() -> dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


CONFIG = load_config()


def get_config_value(key: str, default: Any = None) -> Any:
    platform_key = "windows" if os.name == "nt" else "ubuntu"
    webservice_cfg = CONFIG.get("webservice", {})
    platform_ws_cfg = webservice_cfg.get(platform_key, {}) if isinstance(webservice_cfg, dict) else {}

    if isinstance(webservice_cfg, dict) and key in webservice_cfg:
        return webservice_cfg.get(key, default)
    if isinstance(platform_ws_cfg, dict) and key in platform_ws_cfg:
        return platform_ws_cfg.get(key, default)
    return default


WS_URL = os.environ.get("QWEN_WS_URL", str(get_config_value("ws_url", "wss://oc.hust.media/chatbot/gpu")))
WS_HEADERS = get_config_value("ws_headers", ["device: gpu"])
if not isinstance(WS_HEADERS, list) or not WS_HEADERS:
    WS_HEADERS = ["device: gpu"]
RECONNECT_DELAY_SECONDS = int(os.environ.get("QWEN_WS_RECONNECT_DELAY", str(get_config_value("ws_reconnect_delay", 30))))
PING_INTERVAL_SECONDS = int(os.environ.get("QWEN_WS_PING_INTERVAL", str(get_config_value("ws_ping_interval", 20))))
PING_TIMEOUT_SECONDS = int(os.environ.get("QWEN_WS_PING_TIMEOUT", str(get_config_value("ws_ping_timeout", 10))))
HELLO_PAYLOAD = get_config_value("ws_hello_payload", {"message": "chào bạn"})
if not isinstance(HELLO_PAYLOAD, dict):
    HELLO_PAYLOAD = {"message": "chào bạn"}
HTTP_TIMEOUT_SECONDS = float(os.environ.get("QWEN_HTTP_TIMEOUT_SECONDS", str(get_config_value("http_timeout_seconds", 15))))
HTTP_CONNECT_TIMEOUT_SECONDS = float(os.environ.get("QWEN_HTTP_CONNECT_TIMEOUT_SECONDS", str(get_config_value("http_connect_timeout_seconds", 5))))

SESSION = requests.Session()
SESSION.trust_env = False
SESSION.mount("http://", HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=0, pool_block=False))
SESSION.mount("https://", HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=0, pool_block=False))


def log(message: str) -> None:
    print(message, flush=True)


def on_open(ws: WebSocketApp) -> None:
    log("[ws] connected")
    ws.send(json.dumps(HELLO_PAYLOAD, ensure_ascii=False))
    log("[ws] hello sent")


def _parse_json_message(message: str) -> dict[str, Any] | None:
    try:
        data = json.loads(message)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _normalize_data(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value

    try:
        return json.loads(text)
    except Exception:
        return value


def _decode_json_if_possible(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value

    try:
        return json.loads(text)
    except Exception:
        return value


def _normalize_target_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.hostname != "localhost":
        return url
    netloc = "127.0.0.1"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    if parts.username:
        auth = parts.username
        if parts.password:
            auth = f"{auth}:{parts.password}"
        netloc = f"{auth}@{netloc}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _call_http_api(url: str, service: str, data: Any) -> dict[str, Any]:
    method = service.strip().upper()
    if method not in {"GET", "POST"}:
        raise ValueError(f"unsupported service: {service}")

    url = _normalize_target_url(url)
    payload = _normalize_data(data)
    request_kwargs: dict[str, Any] = {
        "url": url,
        "method": method,
        "timeout": (HTTP_CONNECT_TIMEOUT_SECONDS, HTTP_TIMEOUT_SECONDS),
    }

    if method == "GET":
        if isinstance(payload, dict) and payload:
            request_kwargs["params"] = payload
    else:
        if isinstance(payload, (dict, list)):
            request_kwargs["json"] = payload
        elif payload is None:
            request_kwargs["data"] = ""
        else:
            request_kwargs["data"] = str(payload)

    resp = SESSION.request(**request_kwargs)
    body_text = resp.text
    return {
        "ok": True,
        "status": resp.status_code,
        "reason": resp.reason,
        "body": body_text,
    }


def _send_api_response(ws: WebSocketApp, message: dict[str, Any], result: dict[str, Any]) -> None:
    response_payload = {
        "device": "backend",
        "url": message.get("url"),
        "service": message.get("service"),
        "status": result.get("status"),
        "category": "api_response",
        "request_id": message.get("request_id"),
        "data_response": _decode_json_if_possible(result.get("body")),
    }
    ws.send(json.dumps(response_payload, ensure_ascii=False))


def _handle_api_run(ws: WebSocketApp, message: dict[str, Any]) -> None:
    category = message.get("category")
    if category != "api_call":
        return

    url = message.get("url")
    service = message.get("service")
    data = message.get("data")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("api_call message missing valid url")
    if not isinstance(service, str) or not service.strip():
        raise ValueError("api_call message missing valid service")

    t0 = time.perf_counter()
    result = _call_http_api(url.strip(), service, data)
    http_elapsed_ms = (time.perf_counter() - t0) * 1000.0
    try:
        _send_api_response(ws, message, result)
    except Exception as exc:
        log(f"[ws] api_response send error: {exc}")
    total_elapsed_ms = (time.perf_counter() - t0) * 1000.0
    log(
        "[ws] api_call done "
        + json.dumps(
            {
                "url": url,
                "service": service,
                "status": result.get("status"),
                "http_ms": round(http_elapsed_ms, 1),
                "total_ms": round(total_elapsed_ms, 1),
            },
            ensure_ascii=False,
        )
    )


def _dispatch_api_run(ws: WebSocketApp, message: dict[str, Any]) -> None:
    worker = threading.Thread(
        target=_handle_api_run,
        args=(ws, message),
        daemon=True,
        name="qwen-webservice-api-run",
    )
    worker.start()


def on_message(ws: WebSocketApp, message: str) -> None:
    log(f"[ws] message: {message}")
    parsed = _parse_json_message(message)
    if not parsed:
        return
    try:
        _dispatch_api_run(ws, parsed)
    except Exception as exc:
        log(f"[ws] api_call error: {exc}")


def on_error(_: WebSocketApp, error_value: Any) -> None:
    log(f"[ws] error: {error_value}")


def on_close(_: WebSocketApp, close_status_code: Any, close_msg: Any) -> None:
    log(f"[ws] closed code={close_status_code} msg={close_msg}")


def run_once() -> None:
    app = WebSocketApp(
        WS_URL,
        header=WS_HEADERS,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    app.run_forever(
        ping_interval=PING_INTERVAL_SECONDS,
        ping_timeout=PING_TIMEOUT_SECONDS,
    )


def run_forever(stop_event: Optional[threading.Event] = None) -> None:
    stop_event = stop_event or threading.Event()

    if threading.current_thread() is threading.main_thread():
        def handle_signal(signum: int, _: Any) -> None:
            stop_event.set()
            log(f"[ws] signal {signum}, stopping")

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    log(f"[ws] target={WS_URL}")
    log(f"[ws] headers={WS_HEADERS}")
    log(f"[ws] reconnect_delay={RECONNECT_DELAY_SECONDS}s")

    while not stop_event.is_set():
        try:
            run_once()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            log(f"[ws] reconnect after error: {exc}")

        if stop_event.is_set():
            break

        log(f"[ws] sleeping {RECONNECT_DELAY_SECONDS}s before reconnect")
        for _ in range(RECONNECT_DELAY_SECONDS):
            if stop_event.is_set():
                break
            time.sleep(1)


def start_background_worker() -> threading.Thread:
    stop_event = threading.Event()
    thread = threading.Thread(target=run_forever, args=(stop_event,), daemon=True, name="qwen-webservice")
    thread.start()
    return thread


def main() -> None:
    run_forever()


if __name__ == "__main__":
    main()
