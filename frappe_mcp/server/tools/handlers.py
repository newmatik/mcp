from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any

from pydantic import ValidationError

import frappe_mcp.server.tools as tools
from frappe_mcp.server import types
from frappe_mcp.server.tools.errors import ToolError


def handle_call_tool(params, tool_registry: OrderedDict[str, tools.Tool]):
    """
    Handles the tools/call request from the client.
    """
    call_params = types.CallToolRequestParams.model_validate(params)
    tool_name = call_params.name
    arguments = call_params.arguments or {}

    if tool_name not in tool_registry:
        # The server answers a ValueError with JSON-RPC -32602 (Invalid params),
        # as the spec asks for unknown tools.
        raise ValueError(f"Unknown tool: {tool_name}")

    tool_info = tool_registry[tool_name]
    fn = tool_info.get('fn')

    if not fn:
        error_content = types.TextContent(
            text=f"Tool '{tool_name}' has no associated function."
        )
        result = types.CallToolResult(content=[error_content], isError=True)
        return result.model_dump(exclude_none=True, by_alias=True)

    try:
        return _get_result(fn, arguments)
    except ToolError as e:
        error_content = types.TextContent(text=e.message)
        result = types.CallToolResult(
            content=[error_content], structuredContent=e.structured_content, isError=True
        )
        return result.model_dump(exclude_none=True, by_alias=True)
    except Exception as e:
        error_content = types.TextContent(text=f"Error calling tool '{tool_name}': {e}")
        result = types.CallToolResult(content=[error_content], isError=True)
        return result.model_dump(exclude_none=True, by_alias=True)


def _get_result(fn, arguments):
    # TODO: check if tool_result is list of content blocks, if so, return it as is

    tool_result = fn(**arguments)
    content = types.TextContent(text='')
    if isinstance(tool_result, str):
        content.text = tool_result

    structured = None
    try:
        content.text = content.text or json.dumps(tool_result)
        if isinstance(tool_result, dict):
            structured = tool_result
    except Exception:
        content.text = content.text or str(tool_result)

    result = types.CallToolResult(
        content=[content], structuredContent=structured, isError=False
    )

    return result.model_dump(exclude_none=True, by_alias=True)


def handle_list_tools(params, tool_registry: OrderedDict[str, tools.Tool]):
    """
    Handles the tools/list request from the client.
    https://modelcontextprotocol.io/specification/2025-06-18/tools/list#toolslist
    """
    # TODO: add pagination support
    types.ListToolsRequestParams.model_validate(params)

    tool_list = []
    # Sorted by name so the list, and a client's prompt cache, stays the
    # same however the tools were imported.
    for _, tool_info in sorted(tool_registry.items()):
        if tool := get_validated_tool(tool_info):
            tool_list.append(tool)

    result = types.ListToolsResult(tools=tool_list, nextCursor=None)
    return result.model_dump(exclude_none=True, by_alias=True)


def get_validated_tool(tool: tools.Tool):
    t = {
        'name': tool.get('name'),
        'description': tool.get('description'),
        'inputSchema': tool.get('input_schema'),
        'outputSchema': tool.get('output_schema'),
        'annotations': tool.get('annotations'),
    }

    if t['outputSchema'] is None:
        del t['outputSchema']
    if t['annotations'] is None:
        del t['annotations']

    try:
        return types.Tool.model_validate(t)
    except ValidationError as e:
        print(e)
    return None


def safe_dumps(data: Any) -> str:
    try:
        return json.dumps(data)
    except Exception:
        return str(data)
