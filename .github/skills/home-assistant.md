---
name: home-assistant
description: "Build on top of the Home Assistant ecosystem, api and integrations. Use this skill when the user asks to build anything related to Home Assistant (commonly abbreviated as HA). It points to documentation files to be read for better understanding of how to connect with Home Assistant. 
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

## Home Assistant documentation
- Rest API: https://developers.home-assistant.io/docs/api/rest
- Websocket API: 
  * https://developers.home-assistant.io/docs/api/websocket/
  * https://raw.githubusercontent.com/home-assistant/core/refs/heads/dev/homeassistant/components/history/websocket_api.py
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
  * For EMHASS see [emhass.md](emhass.md)
