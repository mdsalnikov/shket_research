"""Error classification for self-healing system.

Classifies errors into categories:
- RECOVERABLE: Can retry with adjusted approach
- CONTEXT_OVERFLOW: Need to compress context before retry
- RATE_LIMIT: Wait and retry (backoff)
- FATAL: Cannot recover, need fallback response
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of error types for healing strategies."""

    RECOVERABLE = auto()  # Can retry with adjusted approach
    CONTEXT_OVERFLOW = auto()  # Need to compress context before retry
    RATE_LIMIT = auto()  # Need to wait before retry
    USAGE_LIMIT = auto()  # Account/quota limit - cannot retry
    AUTH_ERROR = auto()  # Authentication error - cannot retry
    FATAL = auto()  # Cannot recover, need fallback
    NETWORK_ERROR = auto()  # Network issues - retry with backoff
    TIMEOUT = auto()  # Request timeout - retry with backoff
    UNKNOWN = auto()  # Unknown error, treat as recoverable


@dataclass
class ClassifiedError:
    """Classified error with metadata for healing decisions.

    Attributes:
        error_type: Classification of the error
        original_error: The original exception
        message: Error message
        is_retryable: Whether retry makes sense
        suggested_action: Suggested healing action
        metadata: Additional context (e.g., wait time for rate limits)

    """

    error_type: ErrorType
    original_error: Exception
    message: str
    is_retryable: bool
    suggested_action: str
    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ErrorClassifier:
    """Classifies errors for appropriate healing strategies.

    Uses pattern matching on error messages and exception types
    to determine the best recovery strategy.

    Example:
        classifier = ErrorClassifier()
        classified = classifier.classify(ValueError("context too long"))
        if classified.error_type == ErrorType.CONTEXT_OVERFLOW:
            # Compress context and retry

    """

    # Error message patterns for classification
    CONTEXT_OVERFLOW_PATTERNS = [
        r"context.*too.*long",
        r"context.*length.*exceed",
        r"token.*limit.*exceed",
        r"max.*context.*length",
        r"context.*window.*exceeded",
        r"conversation.*too.*long",
        r"message.*too.*long",
        r"prompt.*too.*long",
        r"input.*length.*exceed",
        r"exceeds.*maximum.*tokens",
        r"output.*tokens.*exceed",
        r"completion.*too.*long",
        r"response.*length.*exceed",
    ]

    RATE_LIMIT_PATTERNS = [
        r"rate.*limit",
        r"too.*many.*request",
        r"request.*throttl",
        r"slow.*down",
        r"retry.*after",
        r"429",
        r"exceeds.*rate.*limit",
        r"rate.*exceeded",
        r"requests.*per.*minute",
        r"requests.*per.*second",
        r"api.*limit",
    ]

    USAGE_LIMIT_PATTERNS = [
        r"usage.*limit.*exceed",
        r"quota.*exceed",
        r"insufficient.*quota",
        r"billing.*limit",
        r"credit.*limit",
        r"account.*limit",
        r"monthly.*limit",
        r"daily.*limit",
        r"subscription.*limit",
        r"plan.*limit",
        r"free.*tier.*limit",
    ]

    AUTH_ERROR_PATTERNS = [
        r"invalid.*api.*key",
        r"authentication.*fail",
        r"unauthorized",
        r"401",
        r"403",
        r"permission.*denied",
        r"access.*denied",
        r"invalid.*credential",
        r"token.*expired",
        r"token.*invalid",
        r"bearer.*invalid",
        r"api.*key.*invalid",
        r"api.*key.*not.*found",
    ]

    NETWORK_ERROR_PATTERNS = [
        r"connection.*refused",
        r"connection.*reset",
        r"connection.*timeout",
        r"network.*unreachable",
        r"no.*such.*host",
        r"failed.*to.*resolve",
        r"connection.*error",
        r"socket.*error",
        r"ssl.*error",
        r"certificate.*error",
        r"tls.*error",
    ]

    TIMEOUT_PATTERNS = [
        r"timeout.*exceeded",
        r"request.*timeout",
        r"read.*timeout",
        r"write.*timeout",
        r"connect.*timeout",
        r"operation.*timed.*out",
        r"timed.*out.*while",
        r"deadline.*exceeded",
    ]

    FATAL_PATTERNS = [
        r"model.*not.*found",
        r"model.*unavailable",
        r"service.*unavailable",
        r"internal.*server.*error",
        r"500",
        r"502",
        r"503",
        r"504",
        r"gateway.*timeout",
        r"bad.*gateway",
        r"service.*discovery.*failed",
    ]

    def __init__(self):
        """Initialize classifier with compiled patterns."""
        self._compiled_patterns: dict[ErrorType, list[re.Pattern]] = {
            ErrorType.CONTEXT_OVERFLOW: [
                re.compile(p, re.IGNORECASE) for p in self.CONTEXT_OVERFLOW_PATTERNS
            ],
            ErrorType.RATE_LIMIT: [re.compile(p, re.IGNORECASE) for p in self.RATE_LIMIT_PATTERNS],
            ErrorType.USAGE_LIMIT: [
                re.compile(p, re.IGNORECASE) for p in self.USAGE_LIMIT_PATTERNS
            ],
            ErrorType.AUTH_ERROR: [re.compile(p, re.IGNORECASE) for p in self.AUTH_ERROR_PATTERNS],
            ErrorType.NETWORK_ERROR: [
                re.compile(p, re.IGNORECASE) for p in self.NETWORK_ERROR_PATTERNS
            ],
            ErrorType.TIMEOUT: [re.compile(p, re.IGNORECASE) for p in self.TIMEOUT_PATTERNS],
            ErrorType.FATAL: [re.compile(p, re.IGNORECASE) for p in self.FATAL_PATTERNS],
        }

    def classify(self, error: Exception) -> ClassifiedError:
        """Classify an error for healing strategy selection.

        Args:
            error: The exception to classify

        Returns:
            ClassifiedError with type and recovery suggestions

        """
        message = str(error)

        # Check patterns in order of priority
        # CONTEXT_OVERFLOW is highest priority - we can compress and retry
        if self._matches_patterns(message, ErrorType.CONTEXT_OVERFLOW):
            return ClassifiedError(
                error_type=ErrorType.CONTEXT_OVERFLOW,
                original_error=error,
                message=message,
                is_retryable=True,
                suggested_action="compress_context",
                metadata={"reason": "Context window exceeded"},
            )

        # USAGE_LIMIT - cannot retry, need fallback
        if self._matches_patterns(message, ErrorType.USAGE_LIMIT):
            return ClassifiedError(
                error_type=ErrorType.USAGE_LIMIT,
                original_error=error,
                message=message,
                is_retryable=False,
                suggested_action="fallback_response",
                metadata={"reason": "Usage quota exceeded"},
            )

        # AUTH_ERROR - cannot retry, need fallback
        if self._matches_patterns(message, ErrorType.AUTH_ERROR):
            return ClassifiedError(
                error_type=ErrorType.AUTH_ERROR,
                original_error=error,
                message=message,
                is_retryable=False,
                suggested_action="fallback_response",
                metadata={"reason": "Authentication failed"},
            )

        # NETWORK_ERROR - can retry with exponential backoff
        if self._matches_patterns(message, ErrorType.NETWORK_ERROR):
            return ClassifiedError(
                error_type=ErrorType.NETWORK_ERROR,
                original_error=error,
                message=message,
                is_retryable=True,
                suggested_action="retry_with_backoff",
                metadata={"reason": "Network error", "use_exponential_backoff": True},
            )

        # TIMEOUT - can retry with exponential backoff
        if self._matches_patterns(message, ErrorType.TIMEOUT):
            return ClassifiedError(
                error_type=ErrorType.TIMEOUT,
                original_error=error,
                message=message,
                is_retryable=True,
                suggested_action="retry_with_backoff",
                metadata={"reason": "Request timeout", "use_exponential_backoff": True},
            )

        # RATE_LIMIT - can retry after wait
        if self._matches_patterns(message, ErrorType.RATE_LIMIT):
            wait_seconds = self._extract_wait_time(message)
            return ClassifiedError(
                error_type=ErrorType.RATE_LIMIT,
                original_error=error,
                message=message,
                is_retryable=True,
                suggested_action="wait_and_retry",
                metadata={"wait_seconds": wait_seconds, "reason": "Rate limited"},
            )

        # FATAL errors - cannot retry
        if self._matches_patterns(message, ErrorType.FATAL):
            return ClassifiedError(
                error_type=ErrorType.FATAL,
                original_error=error,
                message=message,
                is_retryable=False,
                suggested_action="fallback_response",
                metadata={"reason": "Fatal error"},
            )

        # Default: treat as recoverable
        return ClassifiedError(
            error_type=ErrorType.RECOVERABLE,
            original_error=error,
            message=message,
            is_retryable=True,
            suggested_action="retry_with_context",
            metadata={"reason": "Unknown error, attempting recovery"},
        )

    def _matches_patterns(self, message: str, error_type: ErrorType) -> bool:
        """Check if message matches any pattern for the error type.

        Args:
            message: Error message to check
            error_type: Type of error to check patterns for

        Returns:
            True if any pattern matches

        """
        patterns = self._compiled_patterns.get(error_type, [])
        return any(pattern.search(message) for pattern in patterns)

    def _extract_wait_time(self, message: str) -> int:
        """Extract wait time from rate limit error message.

        Looks for patterns like:
        - "retry after 30 seconds"
        - "try again in 60s"
        - "rate limit resets in 5 minutes"

        Args:
            message: Error message to parse

        Returns:
            Wait time in seconds (default 30 if not found)

        """
        # Look for numeric patterns with time units
        patterns = [
            r"(\d+)\s*(?:seconds?|s)\b",
            r"(\d+)\s*(?:minutes?|m)\b",
            r"(\d+)\s*(?:hours?|h)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                value = int(match.group(1))
                # Convert to seconds based on unit
                unit = match.group(0).lower()
                if "minute" in unit:
                    return value * 60
                elif "hour" in unit:
                    return value * 3600
                return value

        # Default wait time
        return 30

    def should_retry(self, error: Exception, attempt: int, max_attempts: int) -> bool:
        """Determine if we should retry based on error classification.

        Args:
            error: The exception that occurred
            attempt: Current attempt number (0-indexed)
            max_attempts: Maximum allowed attempts

        Returns:
            True if retry is appropriate

        """
        if attempt >= max_attempts - 1:
            return False

        classified = self.classify(error)
        return classified.is_retryable

    def get_backoff_time(self, error: Exception, attempt: int) -> int:
        """Calculate backoff time for retry.

        Uses exponential backoff for network errors and timeouts.
        Uses fixed wait time for rate limits.

        Args:
            error: The exception that occurred
            attempt: Current attempt number (0-indexed)

        Returns:
            Wait time in seconds before retry

        """
        classified = self.classify(error)

        # Rate limit - use extracted wait time
        if classified.error_type == ErrorType.RATE_LIMIT:
            return classified.metadata.get("wait_seconds", 30)

        # Network errors and timeouts - exponential backoff
        if classified.error_type in (ErrorType.NETWORK_ERROR, ErrorType.TIMEOUT):
            # Exponential backoff: 2^attempt * base_delay
            base_delay = 2
            max_delay = 60
            return min(base_delay * (2**attempt), max_delay)

        # Default - small delay
        return 1
