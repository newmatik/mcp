import base64
import hashlib
import json

import pytest
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from frappe_mcp import MCP
from frappe_mcp.server.stateless import CLIENT, REVISION, SERVER, VERSION


@pytest.fixture
def app():
    instance = MCP('staff-fixture', instructions='Use the work order guide.')
    principal = {'can_read': True}
    effects = []

    @instance.tool(
        input_schema={
            'type': 'object',
            'properties': {'region': {'type': 'string', 'x-mcp-header': 'Region'}},
            'required': ['region'],
        }
    )
    def lookup(region: str):
        """Record a fixture lookup."""
        effects.append(region)
        return {'region': region}

    instance.workflows.add(
        'work-orders',
        'Review work orders',
        'Read references/guide.md.',
        files={'references/guide.md': 'Für Köln'},
        visible=lambda: principal['can_read'],
    )
    instance.set_tool_filter(lambda _: principal['can_read'])
    return instance, principal, effects


def send(app, method, params=None, headers=None, *, modern=True):
    params = dict(params or {})
    routing = {}
    if modern:
        params.setdefault('_meta', {VERSION: REVISION, CLIENT: {}})
        routing = {'Mcp-Protocol-Version': REVISION, 'Mcp-Method': method}
        if method in ('tools/call', 'prompts/get', 'resources/read'):
            routing['Mcp-Name'] = params.get(
                'uri' if method == 'resources/read' else 'name', ''
            )
    body = {'jsonrpc': '2.0', 'id': 'sample', 'method': method, 'params': params}
    request = Request(
        EnvironBuilder(
            method='POST',
            path='/mcp',
            json=body,
            headers={**routing, **(headers or {})},
        ).get_environ()
    )
    return app.handle(request, Response())


def test_handshake_and_stateless_clients_share_registry(app):
    server, _, effects = app
    discover = send(server, 'server/discover').json['result']
    assert discover['supportedVersions'] == [REVISION, '2025-03-26']
    assert discover['capabilities']['extensions'] == {
        'io.modelcontextprotocol/skills': {}
    }
    assert discover['_meta'][SERVER]['name'] == 'staff-fixture'
    assert discover['cacheScope'] == 'private'
    assert (
        send(server, 'initialize', modern=False).json['result']['protocolVersion']
        == '2025-03-26'
    )
    assert send(server, 'tools/list').json['result']['tools'][0]['name'] == 'lookup'
    value = 'Köln'
    params = {'name': 'lookup', 'arguments': {'region': value}}
    for bad in (
        {'Mcp-Param-Region': 'Berlin'},
        {'Mcp-Name': 'other'},
        {'Mcp-Method': 'tools/list'},
        {},
    ):
        assert send(server, 'tools/call', params, bad).json['error']['code'] == -32020
    assert effects == []
    encoded = base64.b64encode(value.encode()).decode()
    result = send(
        server, 'tools/call', params, {'Mcp-Param-Region': f'=?base64?{encoded}?='}
    ).json['result']
    assert result['resultType'] == 'complete'
    assert result['structuredContent'] == {'region': 'Köln'}
    assert effects == [value]


def test_workflow_files_and_visibility(app):
    server, principal, _ = app
    entry = send(server, 'skills/list').json['result']['skills'][0]
    assert (
        send(server, 'skills/get', {'uri': entry['uri']}).json['result']['skill']
        == entry
    )
    assert len(entry['resources']) == 2
    for resource in entry['resources']:
        content = (
            send(server, 'resources/read', {'uri': resource['uri']})
            .json['result']['contents'][0]['text']
            .encode()
        )
        assert resource['size'] == len(content)
        assert resource['digest'] == 'sha256:' + hashlib.sha256(content).hexdigest()
    legacy = send(server, 'resources/read', {'uri': entry['uri']}, modern=False).json[
        'result'
    ]
    assert 'resultType' not in legacy
    assert 'Review work orders' in legacy['contents'][0]['text']
    principal['can_read'] = False
    assert send(server, 'skills/list').json['result']['skills'] == []
    assert send(server, 'resources/list').json['result']['resources'] == []
    assert (
        send(server, 'skills/get', {'uri': entry['uri']}).json['error']['code']
        == -32602
    )
    assert (
        send(server, 'resources/read', {'uri': entry['uri']}).json['error']['code']
        == -32602
    )
    assert send(server, 'tools/list').json['result']['tools'] == []


def test_http_errors_do_not_run_tools(app):
    server, _, effects = app
    response = send(
        server,
        'server/discover',
        {'_meta': {VERSION: '2099-01-01', CLIENT: {}}},
        {'Mcp-Protocol-Version': '2099-01-01'},
    )
    assert response.status_code == 400
    assert response.json['error'] == {
        'code': -32022,
        'message': 'Unsupported protocol version',
        'data': {'requested': '2099-01-01', 'supported': [REVISION, '2025-03-26']},
    }
    assert (
        send(server, 'server/discover', {'_meta': {}}).json['error']['code'] == -32602
    )
    assert (
        send(server, 'tools/list', {'cursor': 'absent'}).json['error']['code'] == -32602
    )
    assert (
        send(
            server, 'initialize', headers={'Origin': 'https://other.test'}, modern=False
        ).status_code
        == 403
    )
    for body in ([], {'jsonrpc': '2.0', 'id': False, 'method': 'tools/list'}, 1):
        request = Request(
            EnvironBuilder(
                method='POST', data=json.dumps(body), content_type='application/json'
            ).get_environ()
        )
        response = server.handle(request, Response())
        assert response.status_code == 400
        assert 'id' not in response.json
    assert effects == []
