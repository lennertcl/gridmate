---
name: home-assistant
description: "Build on top of the Home Assistant ecosystem, api and integrations. Use this skill when the user asks to build anything related to Home Assistant (commonly abbreviated as HA). It points to documentation files to be read for better understanding of how to connect with Home Assistant. Also when asked about integrating with different integrations: Nordpool, Solcast, Forecast.Solar, etc."
---

This skill guides interactions with Home Assistant. The entire application
you are building it built on top of an existing Home Assistant layer which 
has several relevant addons integrated. The user configures their devices 
as a one-off inside Home Assistant and can then link these to GridMate 
for energy management purposes. 

The user will provide the guidelines related to what should be built, 
you MUST always fetch and check relevant documentation before starting 
implementation to grasp how aspects of Home Assistant work. 

## Guidelines
When building on top of Home Assistant, aim for reusability of what 
Home Assistant exposes and maximally use its websocket and REST api. 

The essence of what you are building is an application that serves the following tasks: 
- Provides clean, rich and user-friendly dashboard and configuration for energy management
- Simplifies the Home Assistant interface for non-technical users and makes energy 
management accessible to everyone
- Unifies all energy management needs of a user into a single application
- Combines the strengths of Home Assistant, EMHASS and other integrations
into a single application that is powerfull yet elegantly simple to use 

You are NOT: 
- Storing device data such as sensor data or whatever which is already stored
in Home Assistant. But you should fetch this data from it when needed. 
- Rebuilding Home Assistant, simply providing an interface for energy 
management that builds on top of it. 

When writing code that interacts with Home Assistant, ALWAYS CHECK DOCS FIRST from below pages. 

## Websocket API

Frontend pages should use the websocket connection to fetch data and provide realtime 
updating pages. 

`web/static/js/ha-connection.js` handles authentication, URL resolution and connection caching.
Import `get_ha_connection()` from it to get a cached `Connection` object. Import library
functions like `subscribeEntities` directly from `home-assistant-js-websocket`.

```javascript
import { get_ha_connection } from './ha-connection.js';
import { subscribeEntities } from 'https://esm.sh/home-assistant-js-websocket@9.6.0';

const connection = await get_ha_connection();
subscribeEntities(connection, (entities) => { /* ... */ });
```

## MCP-first debugging

When an agent needs to inspect or query Home Assistant during GridMate development, prefer an MCP connection before inventing one-off scripts.

- The workspace-level VS Code configuration lives in `.vscode/mcp.json`.
- The default setup uses a remote HTTP MCP endpoint and prompts for the full MCP URL plus an access token.
- This works with Home Assistant's native `mcp_server` integration at `/api/mcp` and also with HTTP-exposed `ha-mcp` deployments.
- This is the best option for rich agent workflows because it exposes dedicated Home Assistant tools instead of forcing every query through custom shell commands.

There are two valid MCP backends:

- Home Assistant's native `mcp_server` integration exposed from `/api/mcp`.
- `ha-mcp` from `homeassistant-ai/ha-mcp` when it is exposed through HTTP from an addon, proxy, or remote server.

Fallback order for debugging:

1. Use the configured MCP server in VS Code when the task is exploratory or benefits from HA-specific tools.
2. Use GridMate's `gm ha ...` commands when you need deterministic JSON output in the terminal or need to script repeatable checks.
3. Drop to the raw Home Assistant REST or websocket APIs only when the MCP tools or CLI do not cover the required command.

For frontend debugging with real Home Assistant data, use the CLI helpers instead of ad hoc snippets:

- `gm js page-assets --path /dashboard/live`
- `gm js fixture --path /dashboard/live --entity sensor.some_entity`
- `gm js state-stream --entity sensor.some_entity --count 10`

These helpers complement the MCP setup: MCP is best for assistant-side querying and broad HA inspection, while `gm` is best for app-specific, JSON-shaped debug workflows tied to GridMate routes and dashboards.

## Home Assistant documentation
- Rest API: https://developers.home-assistant.io/docs/api/rest
- Websocket API: 
  * https://developers.home-assistant.io/docs/api/websocket/
  * https://raw.githubusercontent.com/home-assistant/core/refs/heads/dev/homeassistant/components/history/websocket_api.py
- MCP:
  * https://github.com/homeassistant-ai/ha-mcp
  * https://www.home-assistant.io/integrations/mcp_server/
- Getting sensor data: 
  * https://www.home-assistant.io/integrations/history/
  * https://www.home-assistant.io/integrations/statistics/
  * https://developers.home-assistant.io/blog/2022/11/16/statistics_refactoring/
- Addon development: 
  * https://developers.home-assistant.io/docs/apps/configuration
  * https://developers.home-assistant.io/docs/apps/communication
  * https://developers.home-assistant.io/docs/apps/presentation
  * https://developers.home-assistant.io/docs/apps/repository
  * https://developers.home-assistant.io/docs/apps/security
- Integrations: 
  * https://www.home-assistant.io/integrations/forecast_solar/
  * https://www.home-assistant.io/integrations/nordpool/
  * https://raw.githubusercontent.com/BJReplay/ha-solcast-solar/refs/heads/main/README.md
  * For EMHASS see [emhass.md](emhass.md)
