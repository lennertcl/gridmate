from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gridmate_cli.runtime import (
    CliError,
    build_doctor_report,
    collect_state_events,
    inspect_page,
    is_process_running,
    load_process_state,
    parse_datetime,
    parse_json_argument,
    print_json,
    read_app_logs,
    remove_process_state,
    request_application,
    resolve_cli_config,
    resolve_ha_connector,
    start_app_process,
    stop_process,
    summarize_routes,
)


def add_app_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--app-url', default=None)
    parser.add_argument('--addon-slug', default=None)


def add_ha_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--ha-url', default=None)
    parser.add_argument('--ha-token', default=None)


def handle_doctor(args: argparse.Namespace) -> int:
    config = resolve_cli_config(app_url=args.app_url, addon_slug=args.addon_slug)
    print_json(build_doctor_report(config))
    return 0


def handle_app_run(args: argparse.Namespace) -> int:
    config = resolve_cli_config(app_url=args.app_url, host=args.host, port=args.port, addon_slug=args.addon_slug)
    return start_app_process(config, debug=args.debug, foreground=args.foreground)


def handle_app_status(args: argparse.Namespace) -> int:
    config = resolve_cli_config(app_url=args.app_url, addon_slug=args.addon_slug)
    process_state = load_process_state(config)
    if not process_state:
        print_json({'running': False, 'reason': 'No managed GridMate process found'})
        return 0

    pid = int(process_state['pid'])
    print_json({'running': is_process_running(pid), **process_state})
    return 0


def handle_app_stop(args: argparse.Namespace) -> int:
    config = resolve_cli_config(app_url=args.app_url, addon_slug=args.addon_slug)
    process_state = load_process_state(config)
    if not process_state:
        raise CliError('No managed GridMate process found')

    pid = int(process_state['pid'])
    stopped = stop_process(pid)
    if stopped:
        remove_process_state(config)
    print_json({'success': stopped, 'pid': pid})
    return 0 if stopped else 1


def handle_app_request(args: argparse.Namespace) -> int:
    config = resolve_cli_config(app_url=args.app_url, addon_slug=args.addon_slug)
    response_payload = request_application(
        config,
        method=args.method,
        path=args.path,
        payload=parse_json_argument(args.json_body, default=None),
        timeout_seconds=args.timeout,
    )

    result = {'success': True, 'response': response_payload}
    if args.tail_logs > 0:
        result['logs'] = read_app_logs(config, lines=args.tail_logs, source=args.logs_source)
    print_json(result)
    return 0


def handle_app_logs(args: argparse.Namespace) -> int:
    config = resolve_cli_config(app_url=args.app_url, addon_slug=args.addon_slug)
    print_json(read_app_logs(config, lines=args.lines, source=args.source))
    return 0


def handle_app_routes(args: argparse.Namespace) -> int:
    print_json({'routes': summarize_routes()})
    return 0


def handle_app_inspect_page(args: argparse.Namespace) -> int:
    config = resolve_cli_config(app_url=args.app_url, addon_slug=args.addon_slug)
    response_payload = request_application(
        config, method='GET', path=args.path, payload=None, timeout_seconds=args.timeout
    )
    body = response_payload['body']
    if not isinstance(body, str):
        raise CliError('Expected HTML page content', {'path': args.path, 'body_type': type(body).__name__})
    print_json({'response': response_payload, 'page': inspect_page(body)})
    return 0


def handle_ha_state(args: argparse.Namespace) -> int:
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    print_json({'entity_id': args.entity_id, 'state': connector.get_state(args.entity_id)})
    return 0


def handle_ha_states(args: argparse.Namespace) -> int:
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    print_json({'states': connector.get_states(args.entity_ids)})
    return 0


def handle_ha_history(args: argparse.Namespace) -> int:
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    print_json(
        {
            'history': connector.get_history(
                args.entity_ids,
                start_time=parse_datetime(args.start),
                end_time=parse_datetime(args.end) if args.end else None,
                minimal_response=not args.full_response,
                significant_changes_only=not args.include_all_changes,
            )
        }
    )
    return 0


def handle_ha_statistics(args: argparse.Namespace) -> int:
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    print_json(
        {
            'statistics': connector.get_statistics(
                args.statistic_ids,
                start_time=parse_datetime(args.start),
                end_time=parse_datetime(args.end) if args.end else None,
                period=args.period,
                types=args.types,
            )
        }
    )
    return 0


def handle_ha_service(args: argparse.Namespace) -> int:
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    payload = parse_json_argument(args.json_body, default={})
    print_json(
        {
            'success': connector.call_service(args.domain, args.service, payload),
            'domain': args.domain,
            'service': args.service,
            'service_data': payload,
        }
    )
    return 0


def handle_ha_rest(args: argparse.Namespace) -> int:
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    payload = parse_json_argument(args.json_body, default=None)
    response = connector.request(args.method, args.path, payload=payload, timeout=args.timeout)
    print_json(
        {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'body': response.json()
            if 'application/json' in response.headers.get('Content-Type', '')
            else response.text,
        }
    )
    return 0


def handle_ha_ws(args: argparse.Namespace) -> int:
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    command = parse_json_argument(args.json_body, default={})
    if not isinstance(command, dict):
        raise CliError('WebSocket command must be a JSON object')
    print_json({'result': connector.websocket_command(command)})
    return 0


def handle_ha_supervisor(args: argparse.Namespace) -> int:
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    payload = parse_json_argument(args.json_body, default=None)
    print_json({'result': connector.supervisor_api(args.endpoint, method=args.method, data=payload)})
    return 0


def handle_ha_addon_logs(args: argparse.Namespace) -> int:
    config = resolve_cli_config(addon_slug=args.addon_slug)
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    print_json(
        {'addon_slug': config.addon_slug, 'lines': connector.get_addon_logs(config.addon_slug, lines=args.lines)}
    )
    return 0


def handle_js_page_assets(args: argparse.Namespace) -> int:
    config = resolve_cli_config(app_url=args.app_url, addon_slug=args.addon_slug)
    response_payload = request_application(
        config, method='GET', path=args.path, payload=None, timeout_seconds=args.timeout
    )
    body = response_payload['body']
    if not isinstance(body, str):
        raise CliError('Expected HTML page content', {'path': args.path, 'body_type': type(body).__name__})
    print_json({'response': response_payload, 'page': inspect_page(body)})
    return 0


def handle_js_fixture(args: argparse.Namespace) -> int:
    config = resolve_cli_config(app_url=args.app_url, addon_slug=args.addon_slug)
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    response_payload = request_application(
        config, method='GET', path=args.path, payload=None, timeout_seconds=args.timeout
    )
    body = response_payload['body']
    if not isinstance(body, str):
        raise CliError('Expected HTML page content', {'path': args.path, 'body_type': type(body).__name__})

    payload = {
        'page_path': args.path,
        'page': inspect_page(body),
        'entities': connector.get_states(args.entities or []) if args.entities else {},
        'api_responses': {},
    }

    if args.include_ha_config:
        payload['api_responses']['/api/ha/config'] = request_application(
            config,
            method='GET',
            path='/api/ha/config',
            payload=None,
            timeout_seconds=args.timeout,
        )

    for api_path in args.api_paths:
        payload['api_responses'][api_path] = request_application(
            config,
            method='GET',
            path=api_path,
            payload=None,
            timeout_seconds=args.timeout,
        )

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = config.project_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(__import__('json').dumps(payload, indent=2), encoding='utf-8')
        payload['output_path'] = output_path

    print_json(payload)
    return 0


def handle_js_state_stream(args: argparse.Namespace) -> int:
    connector = resolve_ha_connector(args.ha_url, args.ha_token)
    print_json(
        {
            'events': collect_state_events(
                connector,
                entity_ids=args.entities,
                count=args.count,
                timeout_seconds=args.timeout,
            )
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='gm', description='GridMate debugging CLI')
    subparsers = parser.add_subparsers(dest='command', required=True)

    doctor_parser = subparsers.add_parser('doctor', help='Inspect the local GridMate debug environment')
    add_app_common_arguments(doctor_parser)
    doctor_parser.set_defaults(handler=handle_doctor)

    app_parser = subparsers.add_parser('app', help='GridMate application debug commands')
    app_subparsers = app_parser.add_subparsers(dest='app_command', required=True)

    app_run_parser = app_subparsers.add_parser('run', help='Start the GridMate Flask app')
    add_app_common_arguments(app_run_parser)
    app_run_parser.add_argument('--host', default=None)
    app_run_parser.add_argument('--port', type=int, default=None)
    app_run_parser.add_argument('--debug', action='store_true')
    app_run_parser.add_argument('--foreground', action='store_true')
    app_run_parser.set_defaults(handler=handle_app_run)

    app_status_parser = app_subparsers.add_parser('status', help='Show the managed app process status')
    add_app_common_arguments(app_status_parser)
    app_status_parser.set_defaults(handler=handle_app_status)

    app_stop_parser = app_subparsers.add_parser('stop', help='Stop the managed app process')
    add_app_common_arguments(app_stop_parser)
    app_stop_parser.set_defaults(handler=handle_app_stop)

    app_request_parser = app_subparsers.add_parser('request', help='Send a JSON request to the GridMate app')
    add_app_common_arguments(app_request_parser)
    app_request_parser.add_argument('--method', default='GET')
    app_request_parser.add_argument('--path', required=True)
    app_request_parser.add_argument('--json-body', default=None)
    app_request_parser.add_argument('--timeout', type=int, default=15)
    app_request_parser.add_argument('--tail-logs', type=int, default=0)
    app_request_parser.add_argument('--logs-source', choices=['auto', 'local', 'addon'], default='auto')
    app_request_parser.set_defaults(handler=handle_app_request)

    app_logs_parser = app_subparsers.add_parser('logs', help='Read recent GridMate logs')
    add_app_common_arguments(app_logs_parser)
    app_logs_parser.add_argument('--lines', type=int, default=100)
    app_logs_parser.add_argument('--source', choices=['auto', 'local', 'addon'], default='auto')
    app_logs_parser.set_defaults(handler=handle_app_logs)

    app_routes_parser = app_subparsers.add_parser('routes', help='List Flask routes')
    app_routes_parser.set_defaults(handler=handle_app_routes)

    app_inspect_parser = app_subparsers.add_parser('inspect-page', help='Inspect page HTML, scripts, and styles')
    add_app_common_arguments(app_inspect_parser)
    app_inspect_parser.add_argument('--path', required=True)
    app_inspect_parser.add_argument('--timeout', type=int, default=15)
    app_inspect_parser.set_defaults(handler=handle_app_inspect_page)

    ha_parser = subparsers.add_parser('ha', help='Home Assistant REST and websocket helpers')
    ha_subparsers = ha_parser.add_subparsers(dest='ha_command', required=True)

    ha_state_parser = ha_subparsers.add_parser('state', help='Fetch a single HA entity state')
    add_ha_common_arguments(ha_state_parser)
    ha_state_parser.add_argument('entity_id')
    ha_state_parser.set_defaults(handler=handle_ha_state)

    ha_states_parser = ha_subparsers.add_parser('states', help='Fetch multiple HA entity states')
    add_ha_common_arguments(ha_states_parser)
    ha_states_parser.add_argument('entity_ids', nargs='+')
    ha_states_parser.set_defaults(handler=handle_ha_states)

    ha_history_parser = ha_subparsers.add_parser('history', help='Fetch HA history for one or more entities')
    add_ha_common_arguments(ha_history_parser)
    ha_history_parser.add_argument('entity_ids', nargs='+')
    ha_history_parser.add_argument('--start', required=True)
    ha_history_parser.add_argument('--end', default=None)
    ha_history_parser.add_argument('--full-response', action='store_true')
    ha_history_parser.add_argument('--include-all-changes', action='store_true')
    ha_history_parser.set_defaults(handler=handle_ha_history)

    ha_statistics_parser = ha_subparsers.add_parser('statistics', help='Fetch HA recorder statistics')
    add_ha_common_arguments(ha_statistics_parser)
    ha_statistics_parser.add_argument('statistic_ids', nargs='+')
    ha_statistics_parser.add_argument('--start', required=True)
    ha_statistics_parser.add_argument('--end', default=None)
    ha_statistics_parser.add_argument('--period', default='5minute')
    ha_statistics_parser.add_argument('--types', nargs='+', default=['mean', 'change', 'max', 'state', 'sum'])
    ha_statistics_parser.set_defaults(handler=handle_ha_statistics)

    ha_service_parser = ha_subparsers.add_parser('service', help='Call a Home Assistant service')
    add_ha_common_arguments(ha_service_parser)
    ha_service_parser.add_argument('domain')
    ha_service_parser.add_argument('service')
    ha_service_parser.add_argument('--json-body', default='{}')
    ha_service_parser.set_defaults(handler=handle_ha_service)

    ha_rest_parser = ha_subparsers.add_parser('rest', help='Run a raw Home Assistant REST request')
    add_ha_common_arguments(ha_rest_parser)
    ha_rest_parser.add_argument('--method', default='GET')
    ha_rest_parser.add_argument('--path', required=True)
    ha_rest_parser.add_argument('--json-body', default=None)
    ha_rest_parser.add_argument('--timeout', type=int, default=30)
    ha_rest_parser.set_defaults(handler=handle_ha_rest)

    ha_ws_parser = ha_subparsers.add_parser('ws', help='Run a raw Home Assistant websocket command')
    add_ha_common_arguments(ha_ws_parser)
    ha_ws_parser.add_argument('--json-body', required=True)
    ha_ws_parser.set_defaults(handler=handle_ha_ws)

    ha_supervisor_parser = ha_subparsers.add_parser('supervisor', help='Run a Supervisor API command through HA')
    add_ha_common_arguments(ha_supervisor_parser)
    ha_supervisor_parser.add_argument('--endpoint', required=True)
    ha_supervisor_parser.add_argument('--method', default='get')
    ha_supervisor_parser.add_argument('--json-body', default=None)
    ha_supervisor_parser.set_defaults(handler=handle_ha_supervisor)

    ha_addon_logs_parser = ha_subparsers.add_parser('addon-logs', help='Fetch GridMate addon logs through HA')
    add_ha_common_arguments(ha_addon_logs_parser)
    ha_addon_logs_parser.add_argument('--addon-slug', default=None)
    ha_addon_logs_parser.add_argument('--lines', type=int, default=100)
    ha_addon_logs_parser.set_defaults(handler=handle_ha_addon_logs)

    js_parser = subparsers.add_parser('js', help='Frontend debugging helpers with live HA data')
    js_subparsers = js_parser.add_subparsers(dest='js_command', required=True)

    js_page_assets_parser = js_subparsers.add_parser('page-assets', help='Inspect the assets loaded by a page')
    add_app_common_arguments(js_page_assets_parser)
    js_page_assets_parser.add_argument('--path', required=True)
    js_page_assets_parser.add_argument('--timeout', type=int, default=15)
    js_page_assets_parser.set_defaults(handler=handle_js_page_assets)

    js_fixture_parser = js_subparsers.add_parser('fixture', help='Capture a page plus live HA state into JSON')
    add_app_common_arguments(js_fixture_parser)
    add_ha_common_arguments(js_fixture_parser)
    js_fixture_parser.add_argument('--path', required=True)
    js_fixture_parser.add_argument('--entity', dest='entities', action='append', default=[])
    js_fixture_parser.add_argument('--api-path', dest='api_paths', action='append', default=[])
    js_fixture_parser.add_argument('--output', default=None)
    js_fixture_parser.add_argument('--timeout', type=int, default=15)
    js_fixture_parser.add_argument('--include-ha-config', action='store_true')
    js_fixture_parser.set_defaults(handler=handle_js_fixture)

    js_state_stream_parser = js_subparsers.add_parser(
        'state-stream', help='Collect live state_changed websocket events'
    )
    add_ha_common_arguments(js_state_stream_parser)
    js_state_stream_parser.add_argument('--entity', dest='entities', action='append', default=[])
    js_state_stream_parser.add_argument('--count', type=int, default=10)
    js_state_stream_parser.add_argument('--timeout', type=float, default=30.0)
    js_state_stream_parser.set_defaults(handler=handle_js_state_stream)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except CliError as exc:
        print_json({'success': False, 'error': exc.message, 'details': exc.details})
        return exc.exit_code
    except KeyboardInterrupt:
        print_json({'success': False, 'error': 'Interrupted'})
        return 130
    except Exception as exc:
        print_json({'success': False, 'error': str(exc), 'type': type(exc).__name__})
        return 1


if __name__ == '__main__':
    sys.exit(main())
