"""Middleware to fix stringified JSON parameters from buggy MCP clients.

This middleware works around a bug in some MCP clients (Claude Code, Cursor) where
nested object parameters are incorrectly stringified before being sent to the server.

GitHub Issues:
- anthropics/claude-code#3084
- anthropics/claude-code#6249

The middleware detects stringified JSON and parses it back to objects before
Pydantic validation, making ADR Kit compatible with buggy clients while remaining
forward-compatible with fixed clients.
"""

import json
import logging
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

logger = logging.getLogger(__name__)


class StringifiedParameterFixMiddleware(Middleware):
    """Fix stringified JSON parameters from buggy MCP clients.

    Some MCP clients (Claude Code, Cursor) have a bug where they stringify
    nested object parameters instead of sending them as proper JSON objects.
    This causes Pydantic validation to fail with errors like:
        '{"choice": "postgresql", ...}' is not of type 'object'

    This middleware intercepts tool calls and detects stringified JSON by:
    1. Checking if a parameter value is a string
    2. Checking if it starts with '{' or '['
    3. Attempting to parse it with json.loads()
    4. Replacing the stringified value with the parsed object

    When clients fix their bugs, this middleware becomes a no-op (harmless passthrough).
    """

    def __init__(self, debug: bool = False) -> None:
        """Initialize the middleware.

        Args:
            debug: If True, log detailed information about parameter fixes
        """
        super().__init__()
        self.debug = debug

    async def on_call_tool(
        self, context: MiddlewareContext, call_next: Any
    ) -> Any:
        """Intercept tool calls and fix stringified parameters.

        Args:
            context: The middleware context containing the tool call message
            call_next: The next middleware or handler in the chain

        Returns:
            The result from the next handler
        """
        if not hasattr(context.message, "arguments"):
            # No arguments to process
            return await call_next(context)

        arguments = context.message.arguments
        if not isinstance(arguments, dict):
            # Arguments are not a dict, can't process
            return await call_next(context)

        # Check each argument for stringified JSON
        fixed_count = 0
        for key, value in list(arguments.items()):
            if self._is_stringified_json(value):
                try:
                    parsed = json.loads(value)
                    arguments[key] = parsed
                    fixed_count += 1

                    if self.debug:
                        logger.info(
                            f"Fixed stringified parameter '{key}' in tool '{context.message.name}'"
                        )
                        logger.debug(f"  Original type: {type(value).__name__}")
                        logger.debug(f"  Parsed type: {type(parsed).__name__}")

                except json.JSONDecodeError as e:
                    # Looks like JSON but isn't valid, leave it as-is
                    if self.debug:
                        logger.warning(
                            f"Parameter '{key}' looks like JSON but failed to parse: {e}"
                        )

        if fixed_count > 0:
            logger.info(
                f"Fixed {fixed_count} stringified parameter(s) in tool '{context.message.name}'"
            )

        # Continue with the (potentially modified) arguments
        return await call_next(context)

    def _is_stringified_json(self, value: Any) -> bool:
        """Check if a value looks like stringified JSON.

        Args:
            value: The value to check

        Returns:
            True if the value appears to be stringified JSON
        """
        if not isinstance(value, str):
            return False

        # Trim whitespace
        trimmed = value.strip()

        # Check if it looks like a JSON object or array
        return (trimmed.startswith("{") and trimmed.endswith("}")) or (
            trimmed.startswith("[") and trimmed.endswith("]")
        )
