#!/usr/bin/env python3
"""Super Agent Bridge — proxies Supervisor API requests."""

import json
import os
import sys

from aiohttp import web, ClientSession

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
SUPERVISOR_URL = "http://supervisor"


def get_bridge_secret() -> str:
    """Read bridge_secret from the add-on options file."""
    try:
        with open("/data/options.json") as f:
            options = json.load(f)
        return options.get("bridge_secret", "")
    except FileNotFoundError:
        return ""


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def supervisor_proxy(request: web.Request) -> web.Response:
    bridge_secret = get_bridge_secret()
    if not bridge_secret:
        return web.json_response(
            {"error": "bridge_secret not configured"}, status=500
        )

    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {bridge_secret}":
        return web.json_response({"error": "unauthorized"}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    method = body.get("method", "GET").upper()
    path = body.get("path", "")
    payload = body.get("body")

    if not path:
        return web.json_response({"error": "path is required"}, status=400)

    url = f"{SUPERVISOR_URL}{path}"
    headers = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}

    async with ClientSession() as session:
        kwargs: dict = {"headers": headers}
        if payload is not None and method in ("POST", "PUT", "PATCH"):
            kwargs["json"] = payload

        async with session.request(method, url, **kwargs) as resp:
            content_type = resp.content_type or ""
            if "json" in content_type:
                data = await resp.json()
                return web.json_response(data, status=resp.status)
            else:
                text = await resp.text()
                return web.Response(text=text, status=resp.status)


def main() -> None:
    if not SUPERVISOR_TOKEN:
        print("ERROR: SUPERVISOR_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post("/supervisor", supervisor_proxy)

    print(f"Super Agent Bridge starting on port 8099")
    web.run_app(app, host="0.0.0.0", port=8099)


if __name__ == "__main__":
    main()
