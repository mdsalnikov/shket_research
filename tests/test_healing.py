"""Tests for self-healing error recovery system."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.healing.classifier import (
    ErrorClassifier,
    ErrorType,
    ClassifiedError,
)
from agent.healing.compressor import ContextCompressor, CompressionResult
from agent.healing.fallback import FallbackHandler, PartialResult
from agent.healing.strategies import (
    HealingStrategy,
    HealingAction,
    SelfHealingRunner,
)


# ============ ErrorClassifier Tests ============

def test_classifier_context_overflow():
    """Context overflow errors are classified correctly."""
    classifier = ErrorClassifier()
    
    # Test various context overflow patterns
    errors = [
        ValueError("context too long"),
        RuntimeError("token limit exceeded"),
        Exception("context window exceeded"),
        RuntimeError("prompt too long"),
    ]
    
    for error in errors:
        classified = classifier.classify(error)
        assert classified.error_type == ErrorType.CONTEXT_OVERFLOW
        assert classified.is_retryable is True
        assert classified.suggested_action == "compress_context"


def test_classifier_usage_limit():
    """Usage limit errors are classified as non-retryable."""
    classifier = ErrorClassifier()
    
    errors = [
        ValueError("usage limit exceeded"),
        RuntimeError("insufficient quota"),
        Exception("billing limit reached"),
        RuntimeError("monthly limit exceeded"),
    ]
    
    for error in errors:
        classified = classifier.classify(error)
        assert classified.error_type == ErrorType.USAGE_LIMIT
        assert classified.is_retryable is False
        assert classified.suggested_action == "fallback_response"


def test_classifier_rate_limit():
    """Rate limit errors are classified with wait time."""
    classifier = ErrorClassifier()
    
    errors = [
        ValueError("rate limit exceeded"),
        RuntimeError("too many requests"),
        Exception("429 error"),
    ]
    
    for error in errors:
        classified = classifier.classify(error)
        assert classified.error_type == ErrorType.RATE_LIMIT
        assert classified.is_retryable is True
        assert classified.suggested_action == "wait_and_retry"
        assert "wait_seconds" in classified.metadata


def test_classifier_rate_limit_extract_wait_time():
    """Wait time is extracted from rate limit message."""
    classifier = ErrorClassifier()
    
    error = ValueError("retry after 30 seconds")
    classified = classifier.classify(error)
    
    assert classified.error_type == ErrorType.RATE_LIMIT
    assert classified.metadata.get("wait_seconds") == 30


def test_classifier_auth_error():
    """Auth errors are classified as non-retryable."""
    classifier = ErrorClassifier()
    
    errors = [
        ValueError("invalid api key"),
        RuntimeError("unauthorized access"),
        Exception("401 forbidden"),
        RuntimeError("permission denied"),
    ]
    
    for error in errors:
        classified = classifier.classify(error)
        assert classified.error_type == ErrorType.AUTH_ERROR
        assert classified.is_retryable is False


def test_classifier_recoverable_default():
    """Unknown errors default to recoverable."""
    classifier = ErrorClassifier()
    
    error = ValueError("some random error")
    classified = classifier.classify(error)
    
    assert classified.error_type == ErrorType.RECOVERABLE
    assert classified.is_retryable is True


def test_classifier_should_retry():
    """should_retry respects error classification."""
    classifier = ErrorClassifier()
    
    # Context overflow - should retry
    assert classifier.should_retry(ValueError("context too long"), 0, 5) is True
    
    # Usage limit - should not retry
    assert classifier.should_retry(ValueError("usage limit exceeded"), 0, 5) is False
    
    # Max attempts reached - should not retry
    assert classifier.should_retry(ValueError("some error"), 4, 5) is False


# ============ ContextCompressor Tests ============

def test_compressor_no_compression_needed():
    """No compression when history is small."""
    compressor = ContextCompressor(keep_recent=10)
    
    history = [{"role": "user", "content": "hello"}]
    result = compressor.compress(history)
    
    assert result.removed_count == 0
    assert result.compressed_history == history
    assert result.compression_ratio == 1.0


def test_compressor_compresses_large_history():
    """Compression removes older messages."""
    compressor = ContextCompressor(keep_recent=5)
    
    history = [
        {"role": "user", "content": f"message {i}"}
        for i in range(20)
    ]
    
    result = compressor.compress(history)
    
    assert result.removed_count > 0
    assert len(result.compressed_history) < len(history)
    assert result.summary is not None


def test_compressor_keeps_recent_messages():
    """Recent messages are preserved."""
    compressor = ContextCompressor(keep_recent=5)
    
    history = [
        {"role": "user", "content": f"message {i}"}
        for i in range(20)
    ]
    
    result = compressor.compress(history)
    
    # Last 5 messages should be preserved
    recent_in_result = result.compressed_history[-5:]
    expected_recent = history[-5:]
    
    assert recent_in_result == expected_recent


def test_compressor_keeps_tool_calls():
    """Tool calls are preserved during compression."""
    compressor = ContextCompressor(keep_recent=3)
    
    history = [
        {"role": "user", "content": "message 1"},
        {"role": "tool", "content": "tool result 1", "tool_name": "read_file"},
        {"role": "user", "content": "message 2"},
        {"role": "tool", "content": "tool result 2", "tool_name": "run_shell"},
        {"role": "user", "content": "message 3"},
        {"role": "assistant", "content": "response"},
    ]
    
    result = compressor.compress(history)
    
    # Tool messages should be preserved
    tool_messages = [m for m in result.compressed_history if m.get("role") == "tool"]
    assert len(tool_messages) >= 1


def test_compressor_estimate_tokens():
    """Token estimation works."""
    compressor = ContextCompressor()
    
    history = [
        {"role": "user", "content": "a" * 100},
        {"role": "assistant", "content": "b" * 200},
    ]
    
    tokens = compressor.estimate_tokens(history)
    assert tokens > 0
    # Roughly (100 + 200) / 4 = 75 tokens
    assert 50 < tokens < 100


# ============ FallbackHandler Tests ============

def test_fallback_generate():
    """Fallback response is generated correctly."""
    handler = FallbackHandler()
    
    partial = PartialResult(
        tool_calls=[
            {"name": "read_file", "result": "file contents"},
            {"name": "run_shell", "result": "command output"},
        ],
        error_message="Context overflow",
        attempt_count=3,
        error_type="context_overflow",
    )
    
    response = handler.generate(partial)
    
    assert "Выполненные действия" in response
    assert "read_file" in response
    assert "run_shell" in response
    assert "Context overflow" in response


def test_fallback_usage_limit():
    """Usage limit fallback has appropriate message."""
    handler = FallbackHandler()
    
    partial = PartialResult(
        error_type="usage_limit",
        error_message="Quota exceeded",
        attempt_count=1,
    )
    
    response = handler.generate(partial)
    
    assert "лимит использования" in response
    assert "Quota exceeded" in response


def test_fallback_from_error():
    """Fallback can be generated directly from error."""
    handler = FallbackHandler()
    
    error = ValueError("usage limit exceeded")
    response = handler.generate_from_error(error, attempt_count=2)
    
    assert "лимит" in response.lower() or "quota" in response.lower()


def test_fallback_retry_prompt():
    """Retry prompt includes error context."""
    handler = FallbackHandler()
    
    error = ValueError("context too long")
    prompt = handler.generate_retry_prompt(
        "analyze files",
        error,
        attempt=1,
        max_attempts=5,
    )
    
    assert "analyze files" in prompt
    assert "Попытка" in prompt or "attempt" in prompt.lower()
    assert "context" in prompt.lower()


# ============ HealingStrategy Tests ============

def test_strategy_determine_action_context_overflow():
    """Context overflow triggers compression."""
    strategy = HealingStrategy()
    
    classified = ClassifiedError(
        error_type=ErrorType.CONTEXT_OVERFLOW,
        original_error=ValueError("context too long"),
        message="context too long",
        is_retryable=True,
        suggested_action="compress_context",
    )
    
    action = strategy.determine_action(classified, 0, 5)
    assert action == HealingAction.COMPRESS_AND_RETRY


def test_strategy_determine_action_usage_limit():
    """Usage limit triggers abort."""
    strategy = HealingStrategy()
    
    classified = ClassifiedError(
        error_type=ErrorType.USAGE_LIMIT,
        original_error=ValueError("usage limit exceeded"),
        message="usage limit exceeded",
        is_retryable=False,
        suggested_action="fallback_response",
    )
    
    action = strategy.determine_action(classified, 0, 5)
    assert action == HealingAction.ABORT


def test_strategy_determine_action_rate_limit():
    """Rate limit triggers wait."""
    strategy = HealingStrategy()
    
    classified = ClassifiedError(
        error_type=ErrorType.RATE_LIMIT,
        original_error=ValueError("rate limit"),
        message="rate limit",
        is_retryable=True,
        suggested_action="wait_and_retry",
    )
    
    action = strategy.determine_action(classified, 0, 5)
    assert action == HealingAction.WAIT_AND_RETRY


def test_strategy_determine_action_fallback_at_max():
    """Fallback at max attempts."""
    strategy = HealingStrategy()
    
    classified = ClassifiedError(
        error_type=ErrorType.RECOVERABLE,
        original_error=ValueError("some error"),
        message="some error",
        is_retryable=True,
        suggested_action="retry_with_context",
    )
    
    action = strategy.determine_action(classified, 4, 5)
    assert action == HealingAction.FALLBACK


# ============ SelfHealingRunner Tests ============

@pytest.mark.asyncio
async def test_runner_success_first_try():
    """Runner succeeds on first attempt."""
    runner = SelfHealingRunner(max_retries=3)
    
    mock_agent = AsyncMock()
    mock_result = MagicMock()
    mock_result.output = "success"
    mock_result.new_messages = MagicMock(return_value=[])
    mock_agent.run.return_value = mock_result

    mock_deps = AsyncMock()
    mock_deps.add_assistant_message = AsyncMock()
    mock_deps.get_model_message_history = AsyncMock(return_value=None)
    mock_deps.set_model_message_history = AsyncMock()

    result, success = await runner.run(
        agent=mock_agent,
        task="test task",
        deps=mock_deps,
    )

    assert success is True
    assert result == "success"
    assert mock_agent.run.call_count == 1


@pytest.mark.asyncio
async def test_runner_retries_retryable_error():
    """Runner retries retryable errors."""
    runner = SelfHealingRunner(max_retries=3)
    
    mock_agent = AsyncMock()
    mock_result = MagicMock()
    mock_result.output = "recovered"
    mock_agent.run.side_effect = [
        ValueError("some error"),  # Recoverable error
        mock_result,
    ]
    mock_result.new_messages = MagicMock(return_value=[])

    mock_deps = AsyncMock()
    mock_deps.add_assistant_message = AsyncMock()
    mock_deps.get_conversation_history = AsyncMock(return_value=[])
    mock_deps.get_model_message_history = AsyncMock(return_value=None)
    mock_deps.set_model_message_history = AsyncMock()

    result, success = await runner.run(
        agent=mock_agent,
        task="test task",
        deps=mock_deps,
    )

    assert success is True
    assert result == "recovered"
    assert mock_agent.run.call_count == 2


@pytest.mark.asyncio
async def test_runner_aborts_on_usage_limit():
    """Runner doesn't retry usage limit errors."""
    runner = SelfHealingRunner(max_retries=5)
    
    mock_agent = AsyncMock()
    mock_agent.run.side_effect = ValueError("usage limit exceeded")

    mock_deps = AsyncMock()
    mock_deps.add_assistant_message = AsyncMock()
    mock_deps.get_conversation_history = AsyncMock(return_value=[])
    mock_deps.get_model_message_history = AsyncMock(return_value=None)
    mock_deps.set_model_message_history = AsyncMock()

    result, success = await runner.run(
        agent=mock_agent,
        task="test task",
        deps=mock_deps,
    )

    # Should not retry - just return fallback
    assert success is False
    assert "лимит" in result.lower() or "limit" in result.lower()
    # Should only call run once (no retries)
    assert mock_agent.run.call_count == 1


def test_runner_should_count_as_retry():
    """Non-retryable errors don't count against retry limit."""
    runner = SelfHealingRunner()
    
    # Context overflow - retryable
    assert runner.should_count_as_retry(ValueError("context too long")) is True
    
    # Usage limit - not retryable
    assert runner.should_count_as_retry(ValueError("usage limit exceeded")) is False
    
    # Auth error - not retryable
    assert runner.should_count_as_retry(ValueError("invalid api key")) is False


def test_runner_get_stats():
    """Runner tracks attempt statistics."""
    runner = SelfHealingRunner()
    
    stats = runner.get_stats()
    
    assert "total_attempts" in stats
    assert "retryable_attempts" in stats


# ============ Integration Tests ============

@pytest.mark.asyncio
async def test_run_with_retry_with_healing():
    """run_with_retry uses self-healing."""
    from agent.core.runner import run_with_retry
    
    with patch("agent.core.agent.build_session_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = "done"
        mock_result.new_messages = MagicMock(return_value=[])
        mock_agent.run.return_value = mock_result
        mock_build.return_value = mock_agent

        with patch("agent.core.runner.AgentDeps") as mock_deps_class:
            mock_deps = AsyncMock()
            mock_deps.add_user_message = AsyncMock()
            mock_deps.add_assistant_message = AsyncMock()
            mock_deps.get_conversation_history = AsyncMock(return_value=[])
            mock_deps.get_model_message_history = AsyncMock(return_value=None)
            mock_deps.set_model_message_history = AsyncMock()
            mock_deps_class.create = AsyncMock(return_value=mock_deps)

            out = await run_with_retry("task", max_retries=3)
            assert out == "done"
            assert mock_agent.run.call_count == 1


@pytest.mark.asyncio
async def test_run_with_retry_non_retryable_error():
    """run_with_retry handles non-retryable errors gracefully."""
    from agent.core.runner import run_with_retry
    
    with patch("agent.core.agent.build_session_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = ValueError("usage limit exceeded")
        mock_build.return_value = mock_agent
        
        with patch("agent.core.runner.AgentDeps") as mock_deps_class:
            mock_deps = AsyncMock()
            mock_deps.add_user_message = AsyncMock()
            mock_deps.add_assistant_message = AsyncMock()
            mock_deps.get_conversation_history = AsyncMock(return_value=[])
            mock_deps.get_model_message_history = AsyncMock(return_value=None)
            mock_deps.set_model_message_history = AsyncMock()
            mock_deps_class.create = AsyncMock(return_value=mock_deps)

            out = await run_with_retry("task", max_retries=5)
            # Should not waste retries on usage limit
            assert "лимит" in out.lower() or "limit" in out.lower()
            # Should only call run once
            assert mock_agent.run.call_count == 1
