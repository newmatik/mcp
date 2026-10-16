from __future__ import annotations

import pytest
from click.testing import CliRunner

from frappe_mcp.cli import run, utils
from frappe_mcp.server import MCP


def _make_mcp(entry=None) -> MCP:
    # mcp.register() needs a Frappe app, so set the entry function directly.
    mcp = MCP('test')
    mcp._mcp_entry_fn = entry or (lambda: None)
    return mcp


def _complete_tool(**overrides):
    tool = {
        'description': 'Does a thing',
        'annotations': {'title': 'T'},
        'input_schema': {
            'properties': {'a': {'type': 'string', 'description': 'An arg'}}
        },
        'output_schema': None,
    }
    tool.update(overrides)
    return tool


def test_get_mcp_url_uses_module_and_function_name():
    def entry():
        pass

    entry.__module__ = 'my_app.api.mcp'
    url = utils.get_mcp_url(entry)

    assert '/api/method/my_app.api.mcp.entry' in url


def test_check_without_handlers_prints_nothing(capsys):
    utils.check('my_app', [])

    assert capsys.readouterr().out == ''


def test_check_reports_unregistered_handler(capsys, monkeypatch):
    monkeypatch.setattr(utils, 'get_app_relative_path', lambda app, p: 'api/mcp.py')
    mcp = MCP('test')  # no entry function registered

    utils.check('my_app', [(None, mcp)])  # type: ignore[list-item]

    out = capsys.readouterr().out
    assert 'my_app:' in out
    assert 'handler not properly registered: api/mcp.py' in out


def test_check_flags_tool_with_missing_metadata(capsys, monkeypatch):
    monkeypatch.setattr(utils, 'get_app_relative_path', lambda app, p: 'api/mcp.py')
    mcp = _make_mcp()
    mcp._tool_registry['bare'] = _complete_tool(  # type: ignore[assignment]
        description='',
        input_schema={'properties': {'x': {}}},
    )

    utils.check('my_app', [(None, mcp)])  # type: ignore[list-item]

    out = capsys.readouterr().out
    assert 'description not set' in out
    assert 'arg' in out and 'type not set' in out


def test_check_reports_handler_error(capsys, monkeypatch):
    monkeypatch.setattr(utils, 'get_app_relative_path', lambda app, p: 'api/mcp.py')

    def broken():
        raise RuntimeError('boom')

    mcp = _make_mcp(broken)

    utils.check('my_app', [(None, mcp)])  # type: ignore[list-item]

    assert 'handler error: boom' in capsys.readouterr().out


def test_check_complete_tool_is_all_good(capsys, monkeypatch):
    monkeypatch.setattr(utils, 'get_app_relative_path', lambda app, p: 'api/mcp.py')
    mcp = _make_mcp()
    mcp._tool_registry['good'] = _complete_tool()  # type: ignore[assignment]

    utils.check('my_app', [(None, mcp)], verbose=True)  # type: ignore[list-item]

    out = capsys.readouterr().out
    assert 'all good' in out
    assert 'not set' not in out


def test_cli_check_outside_frappe_site_reports_it():
    pytest.importorskip('click')
    try:
        import frappe  # noqa: F401
    except ImportError:
        result = CliRunner().invoke(run, ['check'])
        assert 'Not running in a Frappe site' in result.output
    else:
        pytest.skip('frappe is installed')
