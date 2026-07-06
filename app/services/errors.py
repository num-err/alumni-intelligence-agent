"""Shared exception types for external-service integrations."""


class SearchError(Exception):
    """Raised when the Tavily search API call fails or is misconfigured."""


class ClaudeReasoningError(Exception):
    """Raised when the Claude API call fails, is refused, or returns unparseable output."""


class HunterError(Exception):
    """Raised when a Hunter.io API call fails or is misconfigured."""
