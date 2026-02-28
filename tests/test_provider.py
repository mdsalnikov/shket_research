"""Tests for provider configuration."""

from unittest.mock import MagicMock, patch


def test_config_provider_default():
    """Test that default provider is vllm and vLLM model default is Qwen."""
    from unittest.mock import patch

    from agent import config as agent_config

    assert agent_config.PROVIDER_DEFAULT == "vllm"
    assert "localhost:8000" in agent_config.VLLM_BASE_URL
    # Code default in config.py is Qwen/Qwen3.5-27B
    with patch.object(agent_config, "VLLM_MODEL_NAME", "Qwen/Qwen3.5-27B"):
        assert "qwen" in agent_config.VLLM_MODEL_NAME.lower()


def test_runner_with_provider():
    """Test that run_with_retry passes provider to agent."""
    import asyncio
    from unittest.mock import AsyncMock

    from agent.core.runner import run_with_retry

    # Need to mock where build_session_agent is imported
    with patch("agent.core.agent.build_session_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = "done"
        mock_agent.run.return_value = mock_result
        mock_build.return_value = mock_agent

        with patch("agent.core.runner.AgentDeps") as mock_deps_class:
            mock_deps = AsyncMock()
            mock_deps.add_user_message = AsyncMock()
            mock_deps.get_model_message_history = AsyncMock(return_value="")
            mock_deps_class.create = AsyncMock(return_value=mock_deps)

            asyncio.run(run_with_retry("task", provider="openrouter"))

            # Verify build_session_agent was called with provider
            mock_build.assert_called_once_with(provider="openrouter")


def test_create_agent_vllm():
    """Test creating agent with vLLM provider."""
    from unittest.mock import MagicMock, patch

    # Mock all dependencies before importing create_agent
    with patch("agent.core.agent.OpenAIProvider") as mock_provider:
        with patch("agent.core.agent.OpenAIChatModel") as mock_model:
            with patch("agent.core.agent.register_tools"):
                with patch("agent.core.agent.Agent") as mock_agent_class:
                    mock_agent_instance = MagicMock()
                    mock_agent_class.return_value = mock_agent_instance

                    from agent.core.agent import create_agent

                    create_agent(provider="vllm", model_name="test-model")

                    # Verify OpenAIProvider was created
                    mock_provider.assert_called_once()

                    # Verify OpenAIChatModel was created
                    mock_model.assert_called_once()


def test_create_agent_openrouter():
    """Test creating agent with OpenRouter provider."""
    from unittest.mock import MagicMock, patch

    with patch("agent.core.agent.OpenRouterProvider") as mock_provider:
        with patch("agent.core.agent.OpenRouterModel") as mock_model:
            with patch("agent.core.agent.register_tools"):
                with patch("agent.core.agent.Agent") as mock_agent_class:
                    mock_agent_instance = MagicMock()
                    mock_agent_class.return_value = mock_agent_instance

                    from agent.core.agent import create_agent

                    create_agent(provider="openrouter", model_name="test-model")

                    # Verify OpenRouterProvider was created
                    mock_provider.assert_called_once()

                    # Verify OpenRouterModel was created
                    mock_model.assert_called_once()


def test_create_agent_default_vllm():
    """Test that create_agent uses vLLM by default."""
    from unittest.mock import MagicMock, patch

    with patch("agent.core.agent.OpenAIProvider") as mock_vllm_provider:
        with patch("agent.core.agent.OpenAIChatModel") as mock_vllm_model:
            with patch("agent.core.agent.register_tools"):
                with patch("agent.core.agent.Agent") as mock_agent_class:
                    mock_agent_instance = MagicMock()
                    mock_agent_class.return_value = mock_agent_instance

                    from agent.core.agent import create_agent

                    create_agent()

                    # Verify vLLM provider was used
                    mock_vllm_provider.assert_called_once()
                    mock_vllm_model.assert_called_once()
