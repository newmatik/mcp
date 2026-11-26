"""July Streamable HTTP binding. All business dispatch stays in the caller's registry."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any

from werkzeug.datastructures import Headers

REVISION = '2026-07-28'
LEGACY = '2025-03-26'
VERSION = 'io.modelcontextprotocol/protocolVersion'
CLIENT = 'io.modelcontextprotocol/clientCapabilities'
SERVER = 'io.modelcontextprotocol/serverInfo'
CACHE = {'ttlMs': 0, 'cacheScope': 'private'}


class ProtocolError(ValueError):
    def __init__(self, code: int, message: str, data: dict | None = None):
        super().__init__(message)
        self.code = code
        self.data = data


def decoded_header(value):
    if value is None or not re.fullmatch(r'[\t\x20-\x7e]*', value):
        return None
    if value.startswith('=?base64?') and value.endswith('?='):
        try:
            encoded = value[9:-2]
            raw = base64.b64decode(encoded, validate=True)
            return raw.decode() if base64.b64encode(raw).decode() == encoded else None
        except (ValueError, binascii.Error, UnicodeError):
            return None
    return value


def parameter_headers(schema: dict):
    result = {}

    def walk(node, path, reachable):
        if isinstance(node, list):
            for value in node:
                walk(value, path, False)
        if not isinstance(node, dict):
            return
        if 'x-mcp-header' in node:
            name, kind = node['x-mcp-header'], node.get('type')
            if (
                not reachable
                or not path
                or not isinstance(name, str)
                or not re.fullmatch(r"[!#$%&'*+.^_\x60|~a-zA-Z0-9-]+", name)
                or kind not in ('string', 'boolean', 'integer')
            ):
                raise ValueError('Invalid x-mcp-header')
            header = 'mcp-param-' + name.lower()
            if header in result:
                raise ValueError('Duplicate x-mcp-header')
            result[header] = (path, kind)
        for key, child in node.items():
            if key == 'properties' and isinstance(child, dict):
                for prop, value in child.items():
                    walk(value, (*path, prop), reachable)
            elif key in (
                '$defs',
                'definitions',
                'patternProperties',
                'dependentSchemas',
            ) and isinstance(child, dict):
                for value in child.values():
                    walk(value, path, False)
            elif key in (
                'items',
                'prefixItems',
                'contains',
                'additionalProperties',
                'allOf',
                'oneOf',
                'anyOf',
                'not',
                'if',
                'then',
                'else',
                'unevaluatedProperties',
                'unevaluatedItems',
                'propertyNames',
            ):
                walk(child, path, False)

    walk(schema, (), True)
    return result


def validate(headers: Headers, method: str, params: dict, fields: dict):
    def mismatch():
        raise ProtocolError(-32020, 'Routing headers do not match the request')

    meta = params.get('_meta')
    if (
        not isinstance(meta, dict)
        or not isinstance(meta.get(VERSION), str)
        or not isinstance(meta.get(CLIENT), dict)
    ):
        raise ProtocolError(-32602, 'Expected protocol version and client capabilities')
    version = meta[VERSION]
    if headers.get('Mcp-Protocol-Version') != version:
        mismatch()
    if version != REVISION:
        raise ProtocolError(
            -32022,
            'Unsupported protocol version',
            {'requested': version, 'supported': [REVISION]},
        )
    validate_routing(headers, method, params, fields, optional=False)
    if 'requestState' in params or 'inputResponses' in params:
        raise ProtocolError(-32602, 'Unexpected continuation')


def validate_routing(headers, method, params, fields, *, optional):
    def mismatch():
        raise ProtocolError(-32020, 'Routing headers do not match the request')

    if (not optional or 'Mcp-Method' in headers) and headers.get(
        'Mcp-Method'
    ) != method:
        mismatch()
    if method in ('tools/call', 'resources/read', 'prompts/get'):
        name = params.get('uri' if method == 'resources/read' else 'name')
        if (not optional or 'Mcp-Name' in headers) and (
            not isinstance(name, str) or decoded_header(headers.get('Mcp-Name')) != name
        ):
            mismatch()
    elif 'Mcp-Name' in headers:
        mismatch()
    mirrored = {}
    for header, (path, kind) in fields.items():
        value: Any = params.get('arguments')
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if value is None or (optional and header not in headers):
            continue
        wire = decoded_header(headers.get(header))
        mirrored[header] = True
        if wire is None:
            mismatch()
        if kind == 'integer':
            if (
                type(value) not in (int, float)
                or (isinstance(value, float) and not value.is_integer())
                or abs(value) > 2**53 - 1
                or not re.fullmatch(r'-?(?:0|[1-9]\d*)(?:\.0+)?', wire)
                or int(wire.split('.')[0]) != value
            ):
                mismatch()
        elif kind == 'boolean':
            if not isinstance(value, bool) or wire != str(value).lower():
                mismatch()
        elif not isinstance(value, str) or wire != value:
            mismatch()
    if any(
        k.lower().startswith('mcp-param-') and k.lower() not in mirrored
        for k in headers.keys()
    ):
        mismatch()
