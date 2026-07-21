import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, request


SERVER_DIR = Path(__file__).resolve().parents[2] / "qwen" / "qwen3.5_4B_vn" / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from rag import (  # noqa: E402
    CORPUS_PATH,
    EMBED_MODEL_PATH,
    QWEN_COLLECTION_NAME,
    PERSIST_DIR,
    TOP_K_DEFAULT,
    get_rag_index,
    retrieve_context,
)


APP_PORT = int(os.environ.get("QWEN_RAG_TEST_PORT", "8005"))
KILL_PORT_ON_START = os.environ.get("QWEN_RAG_TEST_KILL_PORT_ON_START", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _get_listener_pids(port: int) -> List[int]:
    current_pid = os.getpid()

    def add_pid(pids: List[int], pid: int) -> None:
        if pid <= 1 or pid == current_pid:
            return
        if pid not in pids:
            pids.append(pid)

    try:
        if os.name == "nt":
            result = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                check=True,
            )
            needle = f":{port} "
            pids: List[int] = []
            for line in result.stdout.splitlines():
                if needle not in line or "LISTENING" not in line:
                    continue
                parts = line.split()
                if not parts:
                    continue
                try:
                    pid = int(parts[-1])
                except ValueError:
                    continue
                add_pid(pids, pid)
            return pids

        for cmd in (
            ["fuser", "-n", "tcp", str(port)],
            ["ss", "-ltnp"],
            ["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"],
        ):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            except Exception:
                continue

            pids: List[int] = []
            if cmd[0] == "fuser":
                for token in result.stdout.replace("\n", " ").split():
                    token = token.strip()
                    if token.endswith("c") or token.endswith("m"):
                        token = token[:-1]
                    try:
                        pid = int(token)
                    except ValueError:
                        continue
                    add_pid(pids, pid)
                if pids:
                    return pids

            for token in result.stdout.replace("\n", " ").split():
                if token.startswith("pid="):
                    raw = token.split("=", 1)[1].split(",", 1)[0]
                    try:
                        pid = int(raw)
                    except ValueError:
                        continue
                    add_pid(pids, pid)
                elif token.isdigit():
                    add_pid(pids, int(token))
            if pids:
                return pids
    except Exception:
        return []

    return []


def _kill_port(port: int, label: str) -> None:
    pids = _get_listener_pids(port)
    if not pids:
        print(f"[port] {label} {port} is free", flush=True)
        return

    print(f"[port] {label} {port} already in use, stopping PID(s): {', '.join(map(str, pids))}", flush=True)
    for pid in pids:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True)
            else:
                if pid <= 1:
                    continue
                subprocess.run(["kill", "-9", str(pid)], capture_output=True, text=True)
        except Exception:
            pass


def _serialize_result(result) -> Dict[str, Any]:
    return {
        "query": result.query,
        "contexts": result.contexts,
        "combined_context": result.combined_context,
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    @app.get("/rag/health")
    @app.get("/v1/rag/health")
    def health():
        rag_index = get_rag_index()
        return jsonify(
            {
                "ok": True,
                "tag": "rag",
                "collection": QWEN_COLLECTION_NAME,
                "persist_dir": PERSIST_DIR,
                "corpus_path": CORPUS_PATH,
                "embed_model": EMBED_MODEL_PATH,
                "count": rag_index.collection.count(),
            }
        )

    @app.get("/retrieve")
    @app.post("/retrieve")
    @app.get("/rag/retrieve")
    @app.post("/rag/retrieve")
    @app.get("/v1/rag/retrieve")
    @app.post("/v1/rag/retrieve")
    def retrieve():
        payload: Dict[str, Any] = {}
        if request.method == "POST":
            payload = request.get_json(force=True, silent=True) or {}
        else:
            payload = dict(request.args.items())

        question = payload.get("question", payload.get("query", ""))
        if not isinstance(question, str) or not question.strip():
            return jsonify({"ok": False, "error": "Missing non-empty 'question' or 'query'"}), 400

        top_k = _parse_int(payload.get("top_k", TOP_K_DEFAULT), TOP_K_DEFAULT)
        result = retrieve_context(question.strip(), top_k=top_k)
        return jsonify(
            {
                "ok": True,
                "top_k": top_k,
                **_serialize_result(result),
            }
        )

    return app


def run_server(host: str = "0.0.0.0", port: int = APP_PORT) -> None:
    if KILL_PORT_ON_START:
        _kill_port(port, "rag_test")
    get_rag_index()
    print(f"[startup] rag_test_server host={host} port={port}", flush=True)
    create_app().run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_server()
