import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from websockets.sync.client import connect as ws_connect

logger = logging.getLogger(__name__)


class HAConnector:
    """A connector to manage Home Assistant REST and WebSocket API communication.

    Uses the REST API for simple state queries and health checks.
    Uses the WebSocket API for recorder statistics (efficient pre-aggregated data).
    """

    def __init__(self, ha_url: Optional[str] = None, token: Optional[str] = None):
        """
        Initializes the HAConnector with REST + WebSocket API support.

        Args:
            ha_url: Home Assistant URL (defaults to HA_URL env var or http://homeassistant.local:8123)
            token: Supervisor token (defaults to SUPERVISOR_TOKEN env var)
        """
        is_local_dev = os.environ.get('LOCAL_DEV', '').lower() == 'true'

        if is_local_dev:
            self.token = token or os.environ.get('HA_TOKEN')
            self.ha_url = (ha_url or os.environ.get('HA_URL', 'http://homeassistant.local:8123')).rstrip('/')
        else:
            self.token = token or os.environ.get('SUPERVISOR_TOKEN')
            self.ha_url = (ha_url or 'http://supervisor/core').rstrip('/')

    @property
    def _headers(self) -> Dict[str, str]:
        """Get HTTP headers for REST API requests."""
        headers = {
            'Content-Type': 'application/json',
        }
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    @property
    def _ws_url(self) -> str:
        """Get WebSocket URL from the HTTP URL."""
        url = self.ha_url.replace('http://', 'ws://').replace('https://', 'wss://')
        return f'{url}/api/websocket'

    @property
    def ws_url(self) -> str:
        """Expose the resolved Home Assistant WebSocket URL."""
        return self._ws_url

    # ============================================
    # REST API Methods
    # ============================================

    def is_connected(self) -> bool:
        """Check if we can connect to Home Assistant."""
        try:
            response = requests.get(f'{self.ha_url}/api/', headers=self._headers, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_state(self, entity_id: str, silent: bool = False) -> Optional[Dict]:
        """
        Gets the current state of a single entity via REST API.

        Args:
            entity_id: The ID of the entity (e.g., 'sensor.energy_consumption')
            silent: If True, log failures at DEBUG level instead of WARNING

        Returns:
            Dictionary with entity state data, or None if not found/error
        """
        try:
            response = requests.get(f'{self.ha_url}/api/states/{entity_id}', headers=self._headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            log_fn = logger.debug if silent else logger.warning
            log_fn(f'Failed to get state for {entity_id}: {response.status_code}')
            return None
        except requests.RequestException as e:
            logger.error(f'Error fetching state for {entity_id}: {e}')
            return None

    def get_states(self, entity_ids: List[str], silent: bool = False) -> Dict[str, Optional[Dict]]:
        """
        Gets the current state of multiple entities via REST API.

        Args:
            entity_ids: List of entity IDs to fetch
            silent: If True, log failures at DEBUG level instead of WARNING

        Returns:
            Dictionary mapping entity_id to its state data
        """
        results = {}
        for entity_id in entity_ids:
            results[entity_id] = self.get_state(entity_id, silent=silent)
        return results

    def get_history(
        self,
        entity_ids: List[str],
        start_time: datetime,
        end_time: Optional[datetime] = None,
        minimal_response: bool = True,
        significant_changes_only: bool = True,
    ) -> Optional[List[List[Dict]]]:
        """
        Fetches raw history for given entities via REST API.

        Note: For energy cost calculations, prefer get_statistics() which returns
        efficient pre-aggregated data via WebSocket.

        Args:
            entity_ids: List of entity IDs to fetch history for
            start_time: Start of the period (datetime)
            end_time: End of the period (optional, defaults to now)
            minimal_response: If True, returns minimal state information
            significant_changes_only: If True, only returns significant state changes

        Returns:
            List of entity histories, where each entity's history is a list of state dicts.
            Returns None on error.
        """
        if not entity_ids:
            return []

        try:
            start_str = start_time.isoformat()
            params = {
                'filter_entity_id': ','.join(entity_ids),
                'minimal_response': str(minimal_response).lower(),
                'significant_changes_only': str(significant_changes_only).lower(),
            }
            if end_time:
                params['end_time'] = end_time.isoformat()

            response = requests.get(
                f'{self.ha_url}/api/history/period/{start_str}', headers=self._headers, params=params, timeout=60
            )

            if response.status_code == 200:
                return response.json()
            logger.warning(f'Failed to get history: {response.status_code}')
            return None
        except requests.RequestException as e:
            logger.error(f'Error fetching history: {e}')
            return None

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: int = 30,
    ) -> requests.Response:
        """Perform a raw REST request against Home Assistant."""
        normalized_path = path if path.startswith('/') else f'/{path}'
        return requests.request(
            method.upper(),
            f'{self.ha_url}{normalized_path}',
            headers=self._headers,
            json=payload,
            params=params,
            timeout=timeout,
        )

    # ============================================
    # WebSocket API Methods
    # ============================================

    def _ws_send_and_receive(self, command: Dict) -> Optional[Dict]:
        """
        Opens a WebSocket connection, authenticates, sends a single command,
        and returns the result. The connection is closed afterwards.

        Args:
            command: The command dict to send (must include 'id' and 'type')

        Returns:
            The result dict on success, or None on error.
        """
        try:
            with ws_connect(self._ws_url) as ws:
                # Step 1: Receive auth_required
                msg = json.loads(ws.recv())
                if msg.get('type') != 'auth_required':
                    logger.error(f'Expected auth_required, got: {msg.get("type")}')
                    return None

                # Step 2: Authenticate
                ws.send(json.dumps({'type': 'auth', 'access_token': self.token}))
                msg = json.loads(ws.recv())
                if msg.get('type') != 'auth_ok':
                    logger.error(f'WebSocket authentication failed: {msg}')
                    return None

                # Step 3: Send command and receive result
                ws.send(json.dumps(command))
                result = json.loads(ws.recv())

                if result.get('success'):
                    return result.get('result', {})
                else:
                    error = result.get('error', {})
                    logger.warning(f'WebSocket command failed: {error.get("code")}: {error.get("message")}')
                    return None

        except Exception as e:
            logger.error(f'WebSocket error: {e}')
            return None

    def get_statistics(
        self,
        statistic_ids: List[str],
        start_time: datetime,
        end_time: Optional[datetime] = None,
        period: str = '5minute',
        types: Optional[List[str]] = None,
    ) -> Optional[Dict[str, List[Dict]]]:
        """
        Fetch pre-aggregated statistics from Home Assistant via WebSocket.

        Automatically splits large requests into smaller chunks (per sensor,
        per time window) to avoid exceeding the WebSocket 1 MB frame limit.

        Args:
            statistic_ids: List of sensor IDs (e.g., ['sensor.energy_consumption'])
            start_time: Start of the period
            end_time: End of the period (optional, defaults to now)
            period: Aggregation period - "5minute", "hour", "day", "week", "month"
            types: Statistics types to include (default: ["mean", "change", "max", "state", "sum"])

        Returns:
            Dict mapping statistic_id to list of stat entries, or None on error.
            Each entry has 'start'/'end' as Unix timestamps in milliseconds,
            plus the requested types (mean, change, max, state, sum, etc.)
        """
        if not statistic_ids:
            return {}

        if types is None:
            types = ['mean', 'change', 'max', 'state', 'sum']

        # Determine chunk size in days based on the aggregation period.
        # 5-minute data produces ~288 entries/sensor/day, so 7 days keeps
        # each response well under the 1 MB WebSocket frame limit.
        chunk_days = self._chunk_days_for_period(period)

        actual_end = end_time or datetime.now()
        total_days = (actual_end - start_time).days

        # If data is small enough, fetch everything in one call
        if total_days <= chunk_days and len(statistic_ids) <= 2:
            return self._fetch_statistics_single(statistic_ids, start_time, actual_end, period, types)

        # Otherwise, fetch one sensor at a time in time-window chunks
        merged: Dict[str, List[Dict]] = {}
        for sensor_id in statistic_ids:
            sensor_entries: List[Dict] = []
            chunk_start = start_time
            while chunk_start < actual_end:
                chunk_end = min(chunk_start + timedelta(days=chunk_days), actual_end)

                result = self._fetch_statistics_single([sensor_id], chunk_start, chunk_end, period, types)
                if result and sensor_id in result:
                    sensor_entries.extend(result[sensor_id])

                chunk_start = chunk_end

            if sensor_entries:
                merged[sensor_id] = sensor_entries

            logger.debug(
                f'Fetched {len(sensor_entries)} entries for {sensor_id} ({start_time.date()} to {actual_end.date()})'
            )

        return merged if merged else None

    @staticmethod
    def _chunk_days_for_period(period: str) -> int:
        """Return the number of days per chunk based on the aggregation period."""
        if period == '5minute':
            return 7  # ~2016 entries per sensor per chunk
        elif period == 'hour':
            return 30  # ~720 entries per sensor per chunk
        else:
            return 365  # day/week/month periods are already small

    def _fetch_statistics_single(
        self,
        statistic_ids: List[str],
        start_time: datetime,
        end_time: datetime,
        period: str,
        types: List[str],
    ) -> Optional[Dict[str, List[Dict]]]:
        """Fetch statistics for a single chunk (sensor list + time window)."""
        command = {
            'id': 1,
            'type': 'recorder/statistics_during_period',
            'start_time': start_time.isoformat(),
            'statistic_ids': statistic_ids,
            'period': period,
            'types': types,
            'end_time': end_time.isoformat(),
        }
        return self._ws_send_and_receive(command)

    def websocket_command(self, command: Dict) -> Optional[Dict]:
        """Send an arbitrary Home Assistant WebSocket command."""
        request = dict(command)
        request.setdefault('id', 1)
        return self._ws_send_and_receive(request)

    # ============================================
    # Addon Discovery Methods
    # ============================================

    def get_addon_hostname(self, addon_slug: str = 'gridmate') -> str:
        supervisor_token = os.environ.get('SUPERVISOR_TOKEN')
        if not supervisor_token:
            return self._detect_addon_hostname_via_ha(addon_slug)

        headers = {'Authorization': f'Bearer {supervisor_token}'}
        try:
            resp = requests.get(
                'http://supervisor/addons/self/info',
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            hostname = resp.json().get('data', {}).get('hostname', '')
            if hostname:
                return hostname
        except requests.RequestException as e:
            logger.debug('Could not fetch own addon info from supervisor: %s', e)

        return self._detect_addon_hostname_via_ha(addon_slug)

    def _detect_addon_hostname_via_ha(self, addon_slug: str) -> str:
        try:
            ws_url = self._ws_url
            import json as _json

            from websockets.sync.client import connect as _ws_connect

            with _ws_connect(ws_url) as ws:
                msg = _json.loads(ws.recv())
                ws.send(_json.dumps({'type': 'auth', 'access_token': self.token}))
                msg = _json.loads(ws.recv())
                if msg.get('type') != 'auth_ok':
                    return addon_slug

                ws.send(
                    _json.dumps(
                        {
                            'id': 1,
                            'type': 'supervisor/api',
                            'endpoint': '/addons',
                            'method': 'get',
                        }
                    )
                )
                resp = _json.loads(ws.recv())
                if not resp.get('success'):
                    return addon_slug

                addons = resp.get('result', {}).get('data', resp.get('result', {})).get('addons', [])
                for addon in addons:
                    slug = addon.get('slug', '')
                    if slug.endswith(f'_{addon_slug}') or slug == addon_slug:
                        return slug.replace('_', '-')
        except Exception as e:
            logger.debug('Could not detect addon hostname via websocket: %s', e)

        return addon_slug

    def supervisor_api(self, endpoint: str, method: str = 'get', data: Optional[Dict] = None) -> Optional[Dict]:
        """Call a Supervisor API endpoint through the HA websocket supervisor bridge."""
        command = {
            'id': 1,
            'type': 'supervisor/api',
            'endpoint': endpoint if endpoint.startswith('/') else f'/{endpoint}',
            'method': method.lower(),
        }
        if data is not None:
            command['data'] = data
        return self._ws_send_and_receive(command)

    def list_addons(self) -> List[Dict]:
        """Return the Supervisor addon list when available."""
        result = self.supervisor_api('/addons')
        if not result:
            return []

        payload = result.get('data', result)
        addons = payload.get('addons', []) if isinstance(payload, dict) else []
        return addons if isinstance(addons, list) else []

    def resolve_addon_slug(self, addon_slug: str = 'gridmate') -> str:
        """Resolve an addon slug to the Supervisor slug used by HA."""
        for addon in self.list_addons():
            slug = addon.get('slug', '')
            if slug == addon_slug or slug.endswith(f'_{addon_slug}'):
                return slug
        return addon_slug

    def get_addon_logs(self, addon_slug: str = 'gridmate', lines: int = 100) -> List[str]:
        """Fetch addon logs via the Supervisor bridge."""
        resolved_slug = self.resolve_addon_slug(addon_slug)
        result = self.supervisor_api(f'/addons/{resolved_slug}/logs')
        if not result:
            return []

        payload = result.get('data', result)
        log_blob = ''
        if isinstance(payload, dict):
            log_blob = payload.get('logs') or payload.get('result') or ''
        elif isinstance(payload, str):
            log_blob = payload

        collected_lines = log_blob.splitlines()
        if lines > 0:
            return collected_lines[-lines:]
        return collected_lines

    # ============================================
    # Service & Automation API Methods
    # ============================================

    def call_service(self, domain: str, service: str, service_data: Optional[Dict] = None) -> bool:
        try:
            response = requests.post(
                f'{self.ha_url}/api/services/{domain}/{service}',
                headers=self._headers,
                json=service_data or {},
                timeout=10,
            )
            if response.status_code == 200:
                return True
            logger.warning(f'Failed to call service {domain}.{service}: {response.status_code}')
            return False
        except requests.RequestException as e:
            logger.error(f'Error calling service {domain}.{service}: {e}')
            return False

    def create_or_update_automation(self, automation_id: str, config: Dict) -> bool:
        try:
            response = requests.post(
                f'{self.ha_url}/api/config/automation/config/{automation_id}',
                headers=self._headers,
                json=config,
                timeout=10,
            )
            if response.status_code == 200:
                logger.info(f'Created/updated automation: {automation_id}')
                return True
            logger.warning(
                f'Failed to create/update automation {automation_id}: {response.status_code} {response.text}'
            )
            return False
        except requests.RequestException as e:
            logger.error(f'Error creating/updating automation {automation_id}: {e}')
            return False

    def delete_automation(self, automation_id: str) -> bool:
        try:
            response = requests.delete(
                f'{self.ha_url}/api/config/automation/config/{automation_id}',
                headers=self._headers,
                timeout=10,
            )
            if response.status_code == 200:
                logger.info(f'Deleted automation: {automation_id}')
                return True
            logger.warning(f'Failed to delete automation {automation_id}: {response.status_code}')
            return False
        except requests.RequestException as e:
            logger.error(f'Error deleting automation {automation_id}: {e}')
            return False

    def get_automations(self) -> List[Dict]:
        try:
            response = requests.get(f'{self.ha_url}/api/states', headers=self._headers, timeout=10)
            if response.status_code == 200:
                return [s for s in response.json() if s.get('entity_id', '').startswith('automation.')]
            logger.warning(f'Failed to get automations: {response.status_code}')
            return []
        except requests.RequestException as e:
            logger.error(f'Error fetching automations: {e}')
            return []

    def reload_automations(self) -> bool:
        return self.call_service('automation', 'reload')
