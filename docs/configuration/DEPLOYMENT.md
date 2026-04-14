# Deployment & Configuration

## Overview

GridMate is a Flask application deployed as a Home Assistant addon running inside a Docker container. It supports two modes of operation controlled by the `LOCAL_DEV` environment variable:

- **Addon mode** (default): Runs inside the HA Supervisor with ingress, reading configuration from `/data/options.json` and using the Supervisor proxy for backend HA communication.
- **Local development mode** (`LOCAL_DEV=true`): Runs on a developer machine connecting to HA via a long-lived access token and IP address.

## Relevant Artefacts

- [config.yaml](../../config.yaml) — HA addon configuration (ingress, options schema)
- [repository.yaml](../../repository.yaml) — HA addon repository metadata
- [translations/en.yaml](../../translations/en.yaml) — Addon option descriptions
- [Dockerfile](../../Dockerfile) — Container image definition
- [run.sh](../../run.sh) — Addon entrypoint script
- [app.py](../../app.py) — Flask application entrypoint (ingress middleware, secret key)
- [web/model/data/ha_connector.py](../../web/model/data/ha_connector.py) — HA API communication
- [web/model/data/data_connector.py](../../web/model/data/data_connector.py) — Persistent settings storage
- [web/routes/dashboards/dashboard.py](../../web/routes/dashboards/dashboard.py) — `/api/ha/config` endpoint
- [web/static/js/ha-connection.js](../../web/static/js/ha-connection.js) — Central frontend HA WebSocket connection module

## Environment Variables

| Variable | Addon Mode | Local Dev | Description |
|---|---|---|---|
| `LOCAL_DEV` | not set | `true` | Switches between addon and local development behaviour |
| `SUPERVISOR_TOKEN` | auto-injected by Supervisor | not used | Server-side token for HA Core API via Supervisor proxy |
| `HA_URL` | not used (auto-detected) | required (e.g. `http://192.168.x.x:8123`) | HA instance URL used by the frontend |
| `HA_TOKEN` | not used (addon option) | required | Long-lived access token for local dev |

In local development mode, these are loaded from an `.env` file by `python-dotenv`.

## Addon Configuration (config.yaml)

Key settings:

- `ingress: true` — Enables ingress so the addon is accessible as a sidebar panel inside the HA UI. Authentication is handled by HA automatically.
- `ingress_port: 8000` — The internal port Flask listens on.
- `panel_icon: mdi:lightning-bolt` — Sidebar icon.
- `homeassistant_api: true` — Grants the addon access to the HA Core REST API through the Supervisor proxy at `http://supervisor/core/api/`.
- `hassio_api: true` — Grants access to the Supervisor API at `http://supervisor/`.
- `hassio_role: manager` — Required so the addon can list installed addons (used to auto-detect the EMHASS addon URL). The detection queries `/addons` to find the EMHASS slug, then fetches `/addons/{slug}/info` for the correct internal hostname (with underscores replaced by hyphens per HA addon DNS rules).
- `init: false` — Required for S6 overlay v3 used by the HA base images.
- `ports: 8000/tcp: 8000` — Exposes port 8000 on the host for direct browser access alongside ingress. The port number can be changed in the addon Network settings.

### Addon Options

| Option | Schema | Description |
|---|---|---|
| `ha_token` | `str?` (optional) | Long-lived access token for the frontend's browser-side WebSocket connection to HA. Required for live dashboards. |

Options are stored in `/data/options.json` by the Supervisor and read directly by the application.

## Ingress

Ingress allows users to access GridMate from within the HA UI as a sidebar panel. The Supervisor reverse-proxies requests to the addon's ingress port and adds the `X-Ingress-Path` header with the base path (e.g. `/api/hassio_ingress/<token>`).

The `IngressMiddleware` in `app.py` sets Flask's `SCRIPT_NAME` from this header so that `url_for()` generates correct URLs behind the proxy. Frontend JavaScript uses the `window.GRIDMATE_BASE` variable (injected from `request.script_root` in `layout.html`) to prefix API calls.

## Repository Structure

This repository doubles as a HA addon repository. The root contains:
- `repository.yaml` — Repository metadata for the HA addon store
- `config.yaml` — Addon configuration (Supervisor finds this via recursive search)

Users can add this repo URL directly in HA to install GridMate.

## Authentication Architecture

### Server-side (backend → HA)

In addon mode, `HAConnector` uses `SUPERVISOR_TOKEN` with `http://supervisor/core` for both REST and WebSocket connections. The Supervisor proxy handles routing to the actual HA Core instance.

In local dev mode, `HAConnector` uses `HA_TOKEN` with the `HA_URL` (direct IP of the HA instance).

### Client-side (browser → HA)

The browser cannot reach `http://supervisor/core` and the `SUPERVISOR_TOKEN` is not valid for direct HA connections. Instead:

- In addon mode: The `/api/ha/config` endpoint reads `ha_token` from `/data/options.json` (addon settings) and auto-detects the HA URL from the Supervisor API (`http://supervisor/core/api/config`).
- In local dev mode: The endpoint reads `HA_TOKEN` and `HA_URL` from the environment.

The frontend uses `web/static/js/ha-connection.js` — a central ES module that wraps `home-assistant-js-websocket`. It fetches the token from `/api/ha/config`, resolves the correct WebSocket URL, and caches the connection. Dashboard scripts import `get_ha_connection()` and `subscribeEntities` from this module instead of interacting with the library directly.

### WebSocket URL Resolution

When running via ingress (`window.GRIDMATE_BASE` is non-empty), the frontend uses `window.location.origin` as the HA WebSocket URL instead of the backend-provided `hass_url`. This ensures the WebSocket connects to the same host the browser used to reach HA, which is critical for remote access scenarios such as Tailscale, Nabu Casa, or any other reverse-proxy setup where the HA internal URL is unreachable from the client.

When running in local dev mode or via direct port access (`window.GRIDMATE_BASE` is empty), the `hass_url` from `/api/ha/config` is used as-is.

### Security

- The long-lived access token is stored in `/data/options.json` (managed by the Supervisor, not in `settings.json`).
- Ingress provides HA-managed authentication — users don't need separate credentials.
- Flask's `SECRET_KEY` is auto-generated and persisted to `/data/.secret_key` in addon mode.
- Direct port access is enabled by default (`ports: 8000/tcp: 8000`) and can be disabled in the addon Network settings.

## Data Persistence

| Mode | Settings Path | Mechanism |
|---|---|---|
| Addon | `/data/settings.json` | HA Supervisor mounts a persistent `/data/` volume automatically |
| Local Dev | `data/settings.json` | Relative path in the project directory |

The `DataConnector` class selects the path based on the `LOCAL_DEV` environment variable.

## Dockerfile

The Dockerfile follows the standard HA addon pattern:
1. Builds from the HA base image (`$BUILD_FROM`) with a fallback default of `ghcr.io/home-assistant/base:latest`
2. Installs Python packages
3. Copies application code to `/app`
4. Uses `CMD [ "/run.sh" ]` as entrypoint (compatible with S6 v3 + `init: false`)

The fallback default keeps local and Supervisor-triggered rebuilds working even if `BUILD_FROM` is not injected explicitly. When Supervisor provides `BUILD_FROM`, that value still takes precedence.

## Local Development Setup

1. Create a long-lived access token in Home Assistant (Profile → Long-Lived Access Tokens)
2. Copy `.env.example` to `.env` and fill in your values:
   ```
   LOCAL_DEV=true
   HA_URL=http://<your-ha-ip>:8123
   HA_TOKEN=<your-long-lived-token>
   ```
3. Run with Flask: `flask --app app.py --debug run`

## Addon Installation

1. Add this repository URL in HA: **Settings → Add-ons → Add-on Store → Repositories**
2. Install the GridMate addon
3. In the addon **Configuration** tab, set `ha_token` to a long-lived access token
4. Start the addon — it appears as a sidebar panel via ingress
