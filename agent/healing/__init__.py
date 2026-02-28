"""Self-healing system for agent error recovery.

This module provides intelligent error handling with:
- Error classification (recoverable vs context_overflow vs fatal)
- Context compression (sliding window + summarization)
- Fallback response generation from partial results
- Coordinated healing strategies

Architecture:
    ErrorClassifier → determines error type
    ContextCompressor → reduces context if needed
    FallbackHandler → generates meaningful fallback
    SelfHealingRunner → orchestrates everything
"""

from agent.healing.classifier import ClassifiedError, ErrorClassifier, ErrorType
from agent.healing.compressor import ContextCompressor
from agent.healing.fallback import FallbackHandler
from agent.healing.strategies import HealingStrategy, SelfHealingRunner

__all__ = [
    "ErrorClassifier",
    "ErrorType",
    "ClassifiedError",
    "ContextCompressor",
    "FallbackHandler",
    "HealingStrategy",
    "SelfHealingRunner",
]
