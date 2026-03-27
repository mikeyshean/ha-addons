#!/usr/bin/env python3
"""Super Agent Bridge — proxies Supervisor API requests and serves config files."""

import json
import os
import sys

from aiohttp import web, ClientSession

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
SUPERVISOR_URL = "http://supervisor"
CONFIG_DIR = "/config"


def get_bridge_secret() -> str:
    """Read bridge_secret from the add-on options file."""
    try:
        with open("/data/options.json") as f:
            options = json.load(f)
        return options.get("bridge_secret", "")
    except FileNotFoundError:
        return ""


def check_auth(request: web.Request) -> str | None:
    """Validate bearer token. Returns error message or None if valid."""
    bridge_secret = get_bridge_secret()
    if not bridge_secret:
        return "bridge_secret not configured"
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {bridge_secret}":
        return "unauthorized"
    return None


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def resolve_config_path(relative_path: str) -> str | None:
    """Resolve a relative path under /config, rejecting traversal."""
    clean = relative_path.lstrip("/")
    if ".." in clean:
        return None
    full = os.path.normpath(os.path.join(CONFIG_DIR, clean))
    if not full.startswith(CONFIG_DIR):
        return None
    return full


async def handle_file_read(method: str, path: str) -> web.Response:
    """Read a file from the HA config directory."""
    relative = path.removeprefix("/files/config")
    resolved = resolve_config_path(relative)
    if resolved is None:
        return web.json_response({"error": "path traversal not allowed"}, status=400)

    if not os.path.isfile(resolved):
        return web.json_response({"error": f"file not found: {relative.lstrip('/')}"}, status=404)

    try:
        with open(resolved, "r") as f:
            content = f.read()
        return web.json_response({"data": {"content": content}})
    except PermissionError:
        return web.json_response({"error": "permission denied"}, status=403)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_file_write(method: str, path: str, payload: dict) -> web.Response:
    """Write a file to the HA config directory."""
    relative = path.removeprefix("/files/config")
    resolved = resolve_config_path(relative)
    if resolved is None:
        return web.json_response({"error": "path traversal not allowed"}, status=400)

    content = payload.get("content") if payload else None
    if content is None:
        return web.json_response({"error": "content is required"}, status=400)

    try:
        parent = os.path.dirname(resolved)
        os.makedirs(parent, exist_ok=True)
        with open(resolved, "w") as f:
            f.write(content)
        return web.json_response({"result": "ok"})
    except PermissionError:
        return web.json_response({"error": "permission denied"}, status=403)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def supervisor_proxy(request: web.Request) -> web.Response:
    auth_error = check_auth(request)
    if auth_error == "bridge_secret not configured":
        return web.json_response({"error": auth_error}, status=500)
    if auth_error:
        return web.json_response({"error": auth_error}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    method = body.get("method", "GET").upper()
    path = body.get("path", "")
    payload = body.get("body")

    if not path:
        return web.json_response({"error": "path is required"}, status=400)

    # File operations — handled locally via /config mount
    if path.startswith("/files/config"):
        if method == "GET":
            return await handle_file_read(method, path)
        elif method == "POST":
            return await handle_file_write(method, path, payload)
        else:
            return web.json_response({"error": f"unsupported method {method} for files"}, status=405)

    # Everything else — proxy to Supervisor API
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

    print("Super Agent Bridge starting on port 8099")
    web.run_app(app, host="0.0.0.0", port=8099)


if __name__ == "__main__":
    main()
