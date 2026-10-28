from __future__ import annotations

from typing import Any

__all__ = ["ToolError"]


class ToolError(Exception):
    """A tool failure returned as an error result with structured content.

    Raise it from a tool to answer with `isError: true`, the message as the
    text content and `structured_content` as `structuredContent`, so clients
    can branch on the kind of error. Any other exception still becomes an
    error result with only a text message.
    """

    def __init__(self, message: str, structured_content: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.structured_content = structured_content
