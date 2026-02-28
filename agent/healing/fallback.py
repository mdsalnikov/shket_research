"""Fallback response generation from partial results.

Creates meaningful responses when agent cannot complete task:
- Uses partial results from tool calls
- Provides structured error information
- Suggests next steps for user
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PartialResult:
    """Partial result from agent execution.
    
    Captures useful information even when execution fails:
    - Tool calls made and their results
    - Messages exchanged
    - Progress made before failure
    
    """
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    user_messages: list[str] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)
    error_message: str | None = None
    attempt_count: int = 1
    error_type: str = "unknown"


class FallbackHandler:
    """Generates meaningful fallback responses from partial results.
    
    Provides graceful degradation:
    - Summarizes what was accomplished
    - Lists tool results that succeeded
    - Explains why task failed
    - Suggests next steps
    
    Example:
        handler = FallbackHandler()
        partial = PartialResult(
            tool_calls=[{"name": "read_file", "result": "..."}],
            error_message="Context overflow",
        )
        response = handler.generate(partial)
        
    """
    
    # Templates for different error types
    TEMPLATES = {
        "usage_limit": {
            "title": "⏸️ Превышен лимит использования",
            "suggestion": "Попробуйте позже или уменьшите сложность задачи.",
            "details": "Достигнут лимит использования API. Это может быть связано с исчерпанием квоты или кредитов.",
        },
        "auth_error": {
            "title": "🔑 Ошибка аутентификации",
            "suggestion": "Проверьте API ключ или обратитесь к администратору.",
            "details": "Не удалось аутентифицироваться. API ключ может быть недействительным или истёк срок его действия.",
        },
        "rate_limit": {
            "title": "⏳ Превышен лимит запросов",
            "suggestion": "Подождите немного и попробуйте снова.",
            "details": "Слишком много запросов за короткое время. Сервер ограничивает частоту запросов.",
        },
        "context_overflow": {
            "title": "📄 Переполнение контекста",
            "suggestion": "Начните новую сессию или упростите задачу.",
            "details": "Разговор стал слишком длинным для обработки моделью. Контекст был сжат или обрезан.",
        },
        "network_error": {
            "title": "🌐 Сетевая ошибка",
            "suggestion": "Проверьте подключение к интернету и попробуйте снова.",
            "details": "Не удалось соединиться с сервером. Проверьте настройки сети.",
        },
        "timeout": {
            "title": "⏱️ Превышено время ожидания",
            "suggestion": "Попробуйте упростить задачу или запустите её снова.",
            "details": "Запрос не был обработан в отведённое время. Сервер может быть перегружен.",
        },
        "fatal": {
            "title": "❌ Критическая ошибка",
            "suggestion": "Обратитесь к администратору.",
            "details": "Произошла непредвиденная ошибка на стороне сервера.",
        },
        "unknown": {
            "title": "⚠️ Ошибка выполнения",
            "suggestion": "Попробуйте упростить задачу или начать заново.",
            "details": "Произошла ошибка, которую не удалось классифицировать.",
        },
    }
    
    def generate(
        self,
        partial: PartialResult,
        include_partial_results: bool = True,
        include_details: bool = True,
    ) -> str:
        """Generate fallback response from partial results.
        
        Args:
            partial: PartialResult with execution state
            include_partial_results: Whether to include tool results
            include_details: Whether to include detailed error information
            
        Returns:
            Meaningful fallback response string
            
        """
        template = self.TEMPLATES.get(
            partial.error_type,
            self.TEMPLATES["unknown"],
        )
        
        parts = [template["title"]]
        parts.append("")  # Empty line
        
        # Add what was accomplished
        if partial.tool_calls and include_partial_results:
            parts.append("**Выполненные действия:**")
            for call in partial.tool_calls[:5]:  # Limit to first 5
                tool_name = call.get("name", "unknown")
                result_summary = self._summarize_result(call.get("result"))
                parts.append(f"• {tool_name}: {result_summary}")
            parts.append("")
        
        # Add progress summary if we have messages
        if partial.assistant_messages and include_partial_results:
            parts.append("**Прогресс:**")
            # Summarize what was accomplished
            progress = self._summarize_progress(partial.assistant_messages)
            if progress:
                parts.append(progress)
            parts.append("")
        
        # Add error information
        if partial.error_message:
            parts.append(f"**Причина остановки:** {partial.error_message}")
            parts.append("")
        
        # Add details if requested
        if include_details and "details" in template:
            parts.append(f"**Информация:** {template['details']}")
            parts.append("")
        
        # Add attempt count
        if partial.attempt_count > 1:
            parts.append(f"**Попыток:** {partial.attempt_count}")
            parts.append("")
        
        # Add suggestion
        parts.append(f"**Рекомендация:** {template['suggestion']}")
        
        return "\n".join(parts)
    
    def _summarize_result(self, result: Any, max_length: int = 100) -> str:
        """Create brief summary of tool result.
        
        Args:
            result: Tool result to summarize
            max_length: Maximum length of summary
            
        Returns:
            Brief summary string
            
        """
        if result is None:
            return "нет результата"
        
        result_str = str(result)
        
        # Truncate if too long
        if len(result_str) > max_length:
            return result_str[:max_length - 3] + "..."
        
        return result_str
    
    def _summarize_progress(self, messages: list[str]) -> str:
        """Summarize progress from assistant messages.
        
        Extracts key accomplishments from the conversation.
        
        Args:
            messages: List of assistant messages
            
        Returns:
            Summary of progress made
            
        """
        if not messages:
            return ""
        
        # Look for key indicators of progress
        progress_indicators = [
            ("файл", "файлы"),
            ("каталог", "каталоги"),
            ("код", "код"),
            ("тест", "тесты"),
            ("исследование", "исследования"),
            ("результат", "результаты"),
        ]
        
        found_items = []
        last_message = messages[-1] if messages else ""
        
        for indicator, plural in progress_indicators:
            if indicator in last_message.lower():
                found_items.append(plural)
        
        if found_items:
            return f"Были обработаны: {', '.join(found_items[:3])}"
        
        # Generic progress summary
        return f"Выполнено {len(messages)} шагов"
    
    def generate_from_error(
        self,
        error: Exception,
        attempt_count: int = 1,
        partial_results: list[dict[str, Any]] | None = None,
    ) -> str:
        """Generate fallback response directly from error.
        
        Convenience method for quick fallback generation.
        
        Args:
            error: The exception that occurred
            attempt_count: Number of attempts made
            partial_results: Optional list of tool call results
            
        Returns:
            Fallback response string
            
        """
        from agent.healing.classifier import ErrorClassifier, ErrorType
        
        classifier = ErrorClassifier()
        classified = classifier.classify(error)
        
        # Map ErrorType to string
        error_type_map = {
            ErrorType.USAGE_LIMIT: "usage_limit",
            ErrorType.AUTH_ERROR: "auth_error",
            ErrorType.RATE_LIMIT: "rate_limit",
            ErrorType.CONTEXT_OVERFLOW: "context_overflow",
            ErrorType.NETWORK_ERROR: "network_error",
            ErrorType.TIMEOUT: "timeout",
            ErrorType.FATAL: "fatal",
            ErrorType.RECOVERABLE: "unknown",
            ErrorType.UNKNOWN: "unknown",
        }
        
        partial = PartialResult(
            tool_calls=partial_results or [],
            error_message=classified.message,
            attempt_count=attempt_count,
            error_type=error_type_map.get(classified.error_type, "unknown"),
        )
        
        return self.generate(partial)
    
    def generate_retry_prompt(
        self,
        original_task: str,
        error: Exception,
        attempt: int,
        max_attempts: int,
    ) -> str:
        """Generate prompt for retry with error context.
        
        Args:
            original_task: Original task description
            error: The exception that occurred
            attempt: Current attempt number (0-indexed)
            max_attempts: Maximum attempts
            
        Returns:
            Prompt string for retry
            
        """
        from agent.healing.classifier import ErrorClassifier
        
        classifier = ErrorClassifier()
        classified = classifier.classify(error)
        
        # Build context-specific retry prompt
        retry_context = (
            f"\n\n[Попытка {attempt + 1}/{max_attempts} не удалась.\n"
            f"Тип ошибки: {classified.error_type.name}\n"
            f"Сообщение: {classified.message}\n"
        )
        
        # Add strategy-specific hint
        if classified.suggested_action == "compress_context":
            retry_context += "\nРекомендация: контекст слишком большой, попробуй использовать более краткие ответы или начни новую сессию.]"
        elif classified.suggested_action == "wait_and_retry":
            retry_context += "\nРекомендация: возник rate limit, подожди немного перед повтором.]"
        elif classified.suggested_action == "retry_with_backoff":
            retry_context += "\nРекомендация: произошла временная ошибка сети или таймаут, попробуй снова с задержкой.]"
        else:
            retry_context += "\nИсправь проблему и выполни задачу снова.]"
        
        return original_task + retry_context


async def create_fallback_from_session(
    deps: Any,
    error: Exception,
    attempt_count: int = 1,
) -> str:
    """Create fallback response from session state.
    
    Extracts partial results from session history and generates
    meaningful fallback response.
    
    Args:
        deps: AgentDeps instance
        error: The exception that occurred
        attempt_count: Number of attempts made
        
    Returns:
        Fallback response string
        
    """
    handler = FallbackHandler()
    
    # Try to extract partial results from session
    partial_results = []
    try:
        if hasattr(deps, 'get_conversation_history'):
            history = await deps.get_conversation_history(limit=20)
            for msg in history:
                if msg.get('role') == 'tool':
                    partial_results.append({
                        'name': msg.get('tool_name', 'unknown'),
                        'result': msg.get('content', ''),
                    })
    except Exception as e:
        logger.debug(f"Could not extract partial results: {e}")
    
    return handler.generate_from_error(error, attempt_count, partial_results)
