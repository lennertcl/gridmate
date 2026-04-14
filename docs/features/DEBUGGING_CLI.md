# Debugging CLI

## Overview

GridMate now includes a JSON-first developer CLI exposed as `gm`. The CLI is designed for agent-driven debugging and repeatable local diagnostics rather than interactive shell workflows. It covers three main areas:

- Running and managing the local Flask application.
- Querying Home Assistant through reusable REST, websocket, and Supervisor-backed helpers.
- Capturing frontend debug data for dashboard JavaScript that depends on live Home Assistant state.

This feature is paired with a workspace-scoped VS Code MCP configuration in `.vscode/mcp.json`. The intended workflow is MCP first for rich Home Assistant inspection in chat, then `gm` for deterministic JSON output tied to GridMate-specific routes, logs, and frontend pages.

The workspace MCP config targets a remote HTTP MCP endpoint rather than a locally spawned stdio server. That keeps the setup compatible with this repository's Python 3.14 development environment while still supporting both of the Home Assistant MCP options relevant to GridMate:

- Home Assistant's native `mcp_server` integration exposed at `/api/mcp`.
- An HTTP-accessible `ha-mcp` endpoint from `homeassistant-ai/ha-mcp`.

## Relevant Artefacts

- [pyproject.toml](../../pyproject.toml) — exposes the `gm` console script
- [.env.example](../../.env.example) — development variables for the CLI and local app URL
- [.vscode/mcp.json](../../.vscode/mcp.json) — workspace Home Assistant MCP configuration for VS Code/Copilot using a remote HTTP endpoint
- [gridmate_cli/main.py](../../gridmate_cli/main.py) — CLI command definitions and argument parsing
- [gridmate_cli/runtime.py](../../gridmate_cli/runtime.py) — shared runtime helpers for process management, HTTP requests, HTML inspection, and websocket streaming
- [web/model/data/ha_connector.py](../../web/model/data/ha_connector.py) — reusable Home Assistant REST, websocket, Supervisor, and addon log helpers used by the CLI
- [README.md](../../README.md) — high-level development usage examples
- [.github/skills/home-assistant.md](../../.github/skills/home-assistant.md) — Home Assistant skill guidance for MCP-first debugging and CLI fallbacks

## Models

The CLI reuses the existing `HAConnector` model instead of creating a second Home Assistant integration path.

### `HAConnector`

The connector now exposes a few lower-level capabilities that are useful for debugging as well as application code:

- `request(method, path, payload, params, timeout)` for raw REST calls.
- `websocket_command(command)` for arbitrary websocket commands.
- `supervisor_api(endpoint, method, data)` for Supervisor requests through Home Assistant.
- `list_addons()`, `resolve_addon_slug()`, and `get_addon_logs()` for addon-aware diagnostics.

Keeping these helpers in the model layer means the CLI does not need to duplicate authentication, URL handling, or Supervisor bridge logic.

## Services

### CLI Runtime

`gridmate_cli/runtime.py` owns the reusable mechanics behind the CLI:

- Resolving `.env` and `.env.local` values.
- Managing the `.gm/` runtime directory for pid and log files.
- Starting and stopping the Flask app as a managed background or foreground process.
- Fetching application pages and extracting scripts, stylesheets, and `window.*` assignments.
- Collecting live `state_changed` websocket events for selected Home Assistant entities.

### CLI Commands

`gridmate_cli/main.py` groups the commands into three areas:

- `gm doctor` inspects the local runtime, MCP config, HA connectivity, and route availability.
- `gm app ...` manages the Flask app, sends JSON requests, reads logs, and lists Flask routes.
- `gm ha ...` provides repeatable Home Assistant queries without dropping to ad hoc curl or websocket snippets.
- `gm js ...` helps debug dashboard JavaScript with real page assets and live Home Assistant data.

### Practical Examples

```bash
gm doctor
gm app run
gm app request --method POST --path /api/optimization/run --json-body '{"type":"dayahead"}' --tail-logs 100
gm ha statistics sensor.energy_consumption --start 2026-04-14T00:00:00 --period hour
gm js fixture --path /dashboard/live --entity sensor.energy_consumption --output data/live-dashboard-fixture.json
gm js state-stream --entity sensor.energy_consumption --count 10
```

## Forms

This feature does not add Flask-WTF forms.

## Routes

This feature does not add new Flask routes. The CLI is intentionally external to the web application and works against existing routes such as:

- `/api/ha/config`
- `/api/optimization/run`
- `/api/optimization/status`
- dashboard pages like `/dashboard/live`

The `gm app routes` command imports the Flask app and enumerates the active route map directly, which is useful when validating route registration without manually scanning the codebase.

## Frontend

This feature does not add new frontend assets. The frontend-related value is in the debug tooling:

- `gm js page-assets` inspects which scripts and stylesheets a page actually loads.
- `gm js fixture` captures page metadata plus selected Home Assistant entity state into a JSON artifact.
- `gm js state-stream` captures real websocket `state_changed` events so dashboard behavior can be debugged against live Home Assistant data rather than synthetic fixtures.

This is especially useful for pages that source their data partly from backend routes and partly from direct Home Assistant websocket subscriptions.