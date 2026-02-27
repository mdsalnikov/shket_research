"""Tests for provider configuration."""

import os
from unittest.mock import patch, MagicMock
import pytest


def test_build_vllm_model():
    """Test building vLLM model."""
    from agent.core.agent import build_vllm_model
    
    with patch("agent.core.agent.OpenAIProvider") as mock_provider:
        with patch("agent.core.agent.OpenAIChatModel") as mock_model:
            model = build_vllm_model(
                model_name="test-model",
                base_url="http://test:8000/v1",
                api_key="test-key",
            )
            
            # Verify OpenAIProvider was created with correct args
            mock_provider.assert_called_once_with(
                base_url="http://test:8000/v1",
                api_key="test-key",
            )
            
            # Verify OpenAIChatModel was created
            mock_model.assert_called_once()


def test_build_openrouter_model():
    """Test building OpenRouter model."""
    from agent.core.agent import build_openrouter_model
    
    with patch("agent.core.agent.OpenRouterProvider") as mock_provider:
        with patch("agent.core.agent.OpenRouterModel") as mock_model:
            model = build_openrouter_model(
                model_name="test-model",
                api_key="test-key",
            )
            
            # Verify OpenRouterProvider was created
            mock_provider.assert_called_once_with(api_key="test-key")
            
            # Verify OpenRouterModel was created
            mock_model.assert_called_once()


def test_build_model_default_vllm():
    """Test that build_model uses vLLM by default."""
    from agent.core.agent import build_model
    
    with patch("agent.core.agent.build_vllm_model") as mock_vllm:
        with patch("agent.core.agent.build_openrouter_model") as mock_or:
            with patch("agent.core.agent.PROVIDER_DEFAULT", "vllm"):
                build_model()
                mock_vllm.assert_called_once()
                mock_or.assert_not_called()


def test_build_model_openrouter():
    """Test that build_model can use OpenRouter."""
    from agent.core.agent import build_model
    
    with patch("agent.core.agent.build_vllm_model") as mock_vllm:
        with patch("agent.core.agent.build_openrouter_model") as mock_or:
            build_model(provider="openrouter")
            mock_or.assert_called_once()
            mock_vllm.assert_not_called()


def test_build_model_passes_args():
    """Test that build_model passes arguments correctly."""
    from agent.core.agent import build_model
    
    with patch("agent.core.agent.build_vllm_model") as mock_vllm:
        with patch("agent.core.agent.PROVIDER_DEFAULT", "vllm"):
            build_model(model_name="custom-model", api_key="custom-key")
            
            # Should be called with model_name and api_key
            call_args = mock_vllm.call_args
            assert call_args[0][0] == "custom-model" or call_args[1].get("model_name") == "custom-model"


def test_config_provider_default():
    """Test that default provider is vllm."""
    from agent.config import PROVIDER_DEFAULT, VLLM_BASE_URL, VLLM_MODEL_NAME
    
    # Check defaults
    assert PROVIDER_DEFAULT == "vllm"
    assert "localhost:8000" in VLLM_BASE_URL
    assert "gpt-oss-120b" in VLLM_MODEL_NAME


def test_runner_with_provider():
    """Test that run_with_retry passes provider to agent."""
    from agent.core.runner import run_with_retry
    from unittest.mock import AsyncMock
    import asyncio
    
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
            mock_deps_class.create = AsyncMock(return_value=mock_deps)
            
            asyncio.run(run_with_retry("task", provider="openrouter"))
            
            # Verify build_session_agent was called with provider
            mock_build.assert_called_once_with(provider="openrouter")
