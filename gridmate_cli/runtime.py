from __future__ import annotations

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional, Sequence
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv
from websockets.sync.client import connect as ws_connect

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.CRITICAL, force=True)

for env_file in (PROJECT_ROOT / '.env', PROJECT_ROOT / '.env.local'):
    if env_file.exists():
        load_dotenv(env_file, override=env_file.name.endswith('.local'))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web.model.data.ha_connector import HAConnector


class CliError(Exception):
    def __init__(self, message: str, details: Optional[Any] = None, exit_code: int = 1):
        super().__init__(message)
        self.message = message
        self.details = details
        self.exit_code = exit_code


@dataclass
class CliConfig:
    project_root: Path
    state_dir: Path
    run_dir: Path
    log_dir: Path
    log_file: Path
    process_file: Path
    app_url: str
    app_host: str
    app_port: int
    addon_slug: str


class PageAssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[dict[str, str]] = []
        self.stylesheets: list[dict[str, str]] = []
        self.title = ''
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attr_map = {key: value or '' for key, value in attrs}
        if tag == 'script' and attr_map.get('src'):
            self.scripts.append(
                {
                    'src': attr_map.get('src', ''),
                    'type': attr_map.get('type', ''),
                }
            )
        if tag == 'link' and 'stylesheet' in attr_map.get('rel', ''):
            self.stylesheets.append(
                {
                    'href': attr_map.get('href', ''),
                    'media': attr_map.get('media', ''),
                }
            )
        if tag == 'title':
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == 'title':
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()


def resolve_cli_config(
    *,
    app_url: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    addon_slug: Optional[str] = None,
) -> CliConfig:
    raw_state_dir = os.environ.get('GRIDMATE_DEBUG_STATE_DIR', '.gm')
    state_dir = Path(raw_state_dir)
    if not state_dir.is_absolute():
        state_dir = PROJECT_ROOT / state_dir

    app_host = host or os.environ.get('GRIDMATE_APP_HOST', '127.0.0.1')
    app_port = port or int(os.environ.get('GRIDMATE_APP_PORT', '8000'))
    resolved_app_url = (app_url or os.environ.get('GRIDMATE_APP_URL') or f'http://{app_host}:{app_port}').rstrip('/')
    resolved_addon_slug = addon_slug or os.environ.get('GRIDMATE_ADDON_SLUG', 'gridmate')

    run_dir = state_dir / 'run'
    log_dir = state_dir / 'logs'
    log_file = log_dir / 'gridmate-app.log'
    process_file = run_dir / 'app-process.json'

    return CliConfig(
        project_root=PROJECT_ROOT,
        state_dir=state_dir,
        run_dir=run_dir,
        log_dir=log_dir,
        log_file=log_file,
        process_file=process_file,
        app_url=resolved_app_url,
        app_host=app_host,
        app_port=app_port,
        addon_slug=resolved_addon_slug,
    )


def ensure_runtime_dirs(config: CliConfig) -> None:
    config.run_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)


def json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f'Object of type {type(value).__name__} is not JSON serializable')


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=False, default=json_default))


def print_json_line(payload: Any) -> None:
    print(json.dumps(payload, sort_keys=False, default=json_default), flush=True)


def parse_json_argument(raw_value: Optional[str], *, default: Optional[Any] = None) -> Any:
    if raw_value is None:
        return default
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise CliError('Invalid JSON argument', {'value': raw_value, 'error': str(exc)}) from exc


def parse_datetime(value: str) -> datetime:
    normalized = value.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CliError('Invalid ISO datetime', {'value': value}) from exc


def parse_response_body(response: requests.Response) -> Any:
    content_type = response.headers.get('Content-Type', '')
    if 'application/json' in content_type:
        try:
            return response.json()
        except ValueError:
            return response.text
    return response.text


def build_url(base_url: str, path: str) -> str:
    normalized_base = f'{base_url.rstrip("/")}/'
    normalized_path = path.lstrip('/')
    return urljoin(normalized_base, normalized_path)


def load_process_state(config: CliConfig) -> Optional[dict[str, Any]]:
    if not config.process_file.exists():
        return None
    try:
        return json.loads(config.process_file.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise CliError('Invalid process state file', {'path': str(config.process_file), 'error': str(exc)}) from exc


def save_process_state(config: CliConfig, payload: dict[str, Any]) -> None:
    ensure_runtime_dirs(config)
    config.process_file.write_text(json.dumps(payload, indent=2, default=json_default), encoding='utf-8')


def remove_process_state(config: CliConfig) -> None:
    if config.process_file.exists():
        config.process_file.unlink()


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_process(pid: int, *, timeout_seconds: float = 5.0) -> bool:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not is_process_running(pid):
            return True
        time.sleep(0.1)

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    return not is_process_running(pid)


def tail_lines(path: Path, count: int) -> list[str]:
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8', errors='replace') as handle:
        lines = handle.readlines()
    return [line.rstrip('\n') for line in lines[-count:]] if count > 0 else [line.rstrip('\n') for line in lines]


def wait_for_app_ready(config: CliConfig, *, timeout_seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = requests.get(config.app_url, timeout=1)
            if response.ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.25)
    return False


def read_app_logs(config: CliConfig, *, lines: int, source: str) -> dict[str, Any]:
    if source == 'local':
        return {
            'source': 'local',
            'path': config.log_file,
            'lines': tail_lines(config.log_file, lines),
        }

    process_state = load_process_state(config)
    local_lines = tail_lines(config.log_file, lines)
    if source == 'auto' and process_state and local_lines:
        return {
            'source': 'local',
            'path': config.log_file,
            'lines': local_lines,
        }

    connector = HAConnector()
    if source == 'addon' or (source == 'auto' and connector.is_connected()):
        return {
            'source': 'addon',
            'addon_slug': config.addon_slug,
            'lines': connector.get_addon_logs(config.addon_slug, lines=lines),
        }

    return {
        'source': 'local',
        'path': config.log_file,
        'lines': tail_lines(config.log_file, lines),
    }


def request_application(
    config: CliConfig,
    *,
    method: str,
    path: str,
    payload: Optional[Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    url = build_url(config.app_url, path)
    response = requests.request(method.upper(), url, json=payload, timeout=timeout_seconds)
    return {
        'url': url,
        'status_code': response.status_code,
        'headers': dict(response.headers),
        'body': parse_response_body(response),
    }


def inspect_page(html: str) -> dict[str, Any]:
    parser = PageAssetParser()
    parser.feed(html)

    window_values: dict[str, Any] = {}
    for name, raw_value in re.findall(r'window\.([A-Za-z0-9_]+)\s*=\s*([^;]+);', html):
        try:
            window_values[name] = json.loads(raw_value)
        except json.JSONDecodeError:
            window_values[name] = raw_value.strip()

    return {
        'title': parser.title,
        'scripts': parser.scripts,
        'stylesheets': parser.stylesheets,
        'window_values': window_values,
        'html_length': len(html),
    }


def summarize_routes() -> list[dict[str, Any]]:
    from app import app as flask_app

    routes = []
    for rule in sorted(flask_app.url_map.iter_rules(), key=lambda item: item.rule):
        routes.append(
            {
                'rule': rule.rule,
                'endpoint': rule.endpoint,
                'methods': sorted(method for method in rule.methods if method not in {'HEAD', 'OPTIONS'}),
            }
        )
    return routes


def start_app_process(config: CliConfig, *, debug: bool, foreground: bool) -> int:
    ensure_runtime_dirs(config)

    command = [sys.executable, '-m', 'flask', '--app', 'app.py']
    if debug:
        command.append('--debug')
    command.extend(['run', '--no-reload', '--host', config.app_host, '--port', str(config.app_port)])

    env = os.environ.copy()
    env.setdefault('LOCAL_DEV', 'true')

    payload = {
        'started_at': datetime.now().isoformat(),
        'command': command,
        'cwd': config.project_root,
        'app_url': config.app_url,
        'log_file': config.log_file,
        'mode': 'foreground' if foreground else 'background',
    }

    if foreground:
        process = subprocess.Popen(
            command,
            cwd=config.project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        payload['pid'] = process.pid
        save_process_state(config, payload)
        print_json_line({'event': 'app_started', **payload})

        assert process.stdout is not None
        for line in process.stdout:
            print_json_line({'event': 'app_log', 'pid': process.pid, 'line': line.rstrip('\n')})

        exit_code = process.wait()
        remove_process_state(config)
        print_json_line({'event': 'app_exit', 'pid': process.pid, 'exit_code': exit_code})
        return exit_code

    with config.log_file.open('a', encoding='utf-8') as handle:
        process = subprocess.Popen(
            command,
            cwd=config.project_root,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )

    payload['pid'] = process.pid
    save_process_state(config, payload)
    ready = wait_for_app_ready(config)
    payload['ready'] = ready
    if ready:
        print_json({'success': True, **payload})
        return 0

    if not is_process_running(process.pid):
        remove_process_state(config)
    print_json({'success': False, **payload, 'log_tail': tail_lines(config.log_file, 20)})
    return 1


def resolve_ha_connector(ha_url: Optional[str], ha_token: Optional[str]) -> HAConnector:
    return HAConnector(ha_url=ha_url, token=ha_token)


def collect_state_events(
    connector: HAConnector,
    *,
    entity_ids: Sequence[str],
    count: int,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    if not connector.token:
        raise CliError('Home Assistant token is required for websocket streaming')

    entity_filter = set(entity_ids)
    collected: list[dict[str, Any]] = []

    with ws_connect(connector.ws_url, open_timeout=timeout_seconds) as ws:
        auth_required = json.loads(ws.recv(timeout=timeout_seconds))
        if auth_required.get('type') != 'auth_required':
            raise CliError('Unexpected websocket handshake', auth_required)

        ws.send(json.dumps({'type': 'auth', 'access_token': connector.token}))
        auth_response = json.loads(ws.recv(timeout=timeout_seconds))
        if auth_response.get('type') != 'auth_ok':
            raise CliError('Websocket authentication failed', auth_response)

        ws.send(json.dumps({'id': 1, 'type': 'subscribe_events', 'event_type': 'state_changed'}))
        subscription_response = json.loads(ws.recv(timeout=timeout_seconds))
        if not subscription_response.get('success'):
            raise CliError('Failed to subscribe to state changes', subscription_response)

        deadline = time.monotonic() + timeout_seconds
        while len(collected) < count and time.monotonic() < deadline:
            remaining = max(deadline - time.monotonic(), 0.1)
            message = json.loads(ws.recv(timeout=remaining))
            if message.get('type') != 'event':
                continue

            event = message.get('event', {})
            data = event.get('data', {})
            entity_id = data.get('entity_id', '')
            if entity_filter and entity_id not in entity_filter:
                continue

            collected.append(
                {
                    'entity_id': entity_id,
                    'new_state': data.get('new_state'),
                    'old_state': data.get('old_state'),
                    'time_fired': event.get('time_fired'),
                }
            )

    return collected


def command_available(command_name: str) -> bool:
    return shutil.which(command_name) is not None


def mask_secret(value: Optional[str]) -> str:
    if not value:
        return ''
    if len(value) <= 8:
        return '*' * len(value)
    return f'{value[:4]}...{value[-4:]}'


def get_workspace_mcp_config() -> Optional[dict[str, Any]]:
    mcp_path = PROJECT_ROOT / '.vscode' / 'mcp.json'
    if not mcp_path.exists():
        return None
    return json.loads(mcp_path.read_text(encoding='utf-8'))


def build_doctor_report(config: CliConfig) -> dict[str, Any]:
    report: dict[str, Any] = {
        'project_root': config.project_root,
        'python_executable': sys.executable,
        'python_version': sys.version,
        'app': {
            'url': config.app_url,
            'host': config.app_host,
            'port': config.app_port,
        },
        'local_dev': os.environ.get('LOCAL_DEV', ''),
        'ha': {
            'ha_url': os.environ.get('HA_URL', ''),
            'ha_token': mask_secret(os.environ.get('HA_TOKEN', '')),
            'supervisor_token_present': bool(os.environ.get('SUPERVISOR_TOKEN')),
        },
        'mcp': get_workspace_mcp_config(),
        'process_state': load_process_state(config),
    }

    try:
        report['routes'] = {
            'count': len(summarize_routes()),
        }
    except Exception as exc:
        report['routes'] = {'error': str(exc)}

    try:
        root_response = requests.get(config.app_url, timeout=3)
        report['app_health'] = {
            'status_code': root_response.status_code,
        }
    except requests.RequestException as exc:
        report['app_health'] = {'error': str(exc)}

    try:
        connector = HAConnector()
        report['ha_connection'] = {
            'reachable': connector.is_connected(),
            'ha_url': connector.ha_url,
        }
    except Exception as exc:
        report['ha_connection'] = {'error': str(exc)}

    return report
