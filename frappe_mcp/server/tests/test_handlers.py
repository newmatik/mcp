from __future__ import annotations

import pytest

from frappe_mcp.server import handlers


def test_handle_initialize_reports_name_and_capabilities():
    result = handlers.handle_initialize({}, 'my-server')

    assert result['serverInfo']['name'] == 'my-server'
    assert result['protocolVersion'] == '2025-03-26'
    assert result['capabilities']['tools'] == {'listChanged': False}
    assert result['capabilities']['prompts'] == {'listChanged': False}
    # Unimplemented capabilities must not be advertised.
    assert 'resources' not in result['capabilities']
    assert 'logging' not in result['capabilities']


def test_handle_ping_returns_empty_dict():
    assert handlers.handle_ping(None) == {}


@pytest.mark.parametrize(
    'fn',
    [
        handlers.handle_complete,
        handlers.handle_set_level,
        handlers.handle_list_resources,
        handlers.handle_list_resource_templates,
        handlers.handle_read_resource,
        handlers.handle_subscribe,
        handlers.handle_unsubscribe,
    ],
)
def test_unimplemented_handlers_raise(fn):
    with pytest.raises(NotImplementedError, match=fn.__name__):
        fn({})


@pytest.mark.parametrize(
    'fn',
    [
        handlers.handle_cancelled,
        handlers.handle_progress,
        handlers.handle_initialized,
        handlers.handle_roots_list_changed,
    ],
)
def test_notification_handlers_are_noops(fn):
    assert fn({}) is None
