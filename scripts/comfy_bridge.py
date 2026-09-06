#!/usr/bin/env python3
"""ComfyUI 中继（在跑 ComfyUI 的机器/沙箱上执行）。

用途：把本机的 ComfyUI（默认 127.0.0.1:8188）以「带 token 的只读代理」方式
暴露出去，让外部工作台服务能直连调用 API（云平台 webview 类地址通常带
登录 cookie 鉴权，服务端请求过不去，这层中继解决的就是这个问题）。

用法：
    python3 comfy_bridge.py                  # 监听 0.0.0.0:9999，转发到 8188
    TOKEN=xxx PORT=9999 UPSTREAM=http://127.0.0.1:8188 python3 comfy_bridge.py

调用方（工作台）配置：
    COMFYUI_URL=http(s)://<公开地址>
    COMFYUI_TOKEN=<同一个 TOKEN>
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

TOKEN = os.getenv("BRIDGE_TOKEN", "nexus-bridge-2026")
PORT = int(os.getenv("BRIDGE_PORT", "9999"))
UPSTREAM = os.getenv("BRIDGE_UPSTREAM", "http://127.0.0.1:8188").rstrip("/")


def relay(method: str, path: str, body: bytes | None, content_type: str | None, token: str | None):
    if token != TOKEN:
        return 403, {"Content-Type": "text/plain; charset=utf-8"}, b"forbidden"
    url = UPSTREAM + path
    req = urllib.request.Request(url, data=body if method == "POST" else None, method=method)
    if body and content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, {}, exc.read() or b"upstream error"
    except Exception as exc:  # noqa: BLE001
        return 502, {"Content-Type": "text/plain; charset=utf-8"}, f"upstream error: {exc}".encode()


def main() -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a):  # 静默
            pass

        def _handle(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            status, headers, payload = relay(
                self.command,
                self.path,
                body,
                self.headers.get("Content-Type"),
                self.headers.get("X-Token"),
            )
            self.send_response(status)
            ct = headers.get("Content-Type", "application/octet-stream")
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)

        do_GET = _handle
        do_POST = _handle

    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[comfy-bridge] listening 0.0.0.0:{PORT} -> {UPSTREAM} (token={TOKEN})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
