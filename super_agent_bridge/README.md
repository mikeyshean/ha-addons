# Super Agent Bridge

A lightweight Home Assistant add-on that proxies Supervisor API requests from Super Agent.

## Setup

1. Add this repository to HA: Settings → Add-ons → Add-on Store → Repositories
2. Install "Super Agent Bridge"
3. Set `bridge_secret` in the add-on configuration (any strong random string)
4. Start the add-on
5. In Super Agent, add `bridgeUrl` and `bridgeSecret` to your HA workspace integration

## How it works

The add-on runs inside HA's Docker network where it has access to the Supervisor API
via the auto-injected `SUPERVISOR_TOKEN`. It exposes an authenticated HTTP endpoint
on port 8099 that Super Agent reaches over Tailscale.

Token rotation on add-on restart is handled transparently — the add-on always reads
the current token from its environment.

### API

`POST /supervisor` — proxy a request to the Supervisor API

```json
{
  "method": "GET",
  "path": "/addons/core_mosquitto/info",
  "body": {}
}
```

`GET /health` — returns `{"status": "ok"}` (no auth required)
