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
