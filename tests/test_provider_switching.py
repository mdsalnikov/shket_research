"""Tests for provider switching functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestProviderCommand:
    """Tests for /provider command in Telegram bot."""

    @pytest.mark.asyncio
    async def test_provider_command_shows_current(self):
        """Test /provider without args shows current provider."""
        from agent.interfaces.telegram import provider_cmd
        
        # Mock update and context
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.username = "testuser"
        update.message = AsyncMock()
        
        context = MagicMock()
        context.args = []
        
        # Mock whitelist check
        with patch("agent.interfaces.telegram._is_user_allowed", return_value=True):
            await provider_cmd(update, context)
        
        # Should show current provider
        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        assert "Current Provider" in call_text

    @pytest.mark.asyncio
    async def test_provider_command_switches_to_vllm(self):
        """Test /provider vllm switches to vLLM."""
        from agent.interfaces.telegram import provider_cmd
        
        # Mock update and context
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.username = "testuser"
        update.message = AsyncMock()
        
        context = MagicMock()
        context.args = ["vllm"]
        
        # Mock whitelist check
        with patch("agent.interfaces.telegram._is_user_allowed", return_value=True):
            await provider_cmd(update, context)
        
        # Should acknowledge switch
        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        assert "vllm" in call_text.lower()

    @pytest.mark.asyncio
    async def test_provider_command_switches_to_openrouter(self):
        """Test /provider openrouter switches to OpenRouter."""
        from agent.interfaces.telegram import provider_cmd
        
        # Mock update and context
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.username = "testuser"
        update.message = AsyncMock()
        
        context = MagicMock()
        context.args = ["openrouter"]
        
        # Mock whitelist check
        with patch("agent.interfaces.telegram._is_user_allowed", return_value=True):
            await provider_cmd(update, context)
        
        # Should acknowledge switch
        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        assert "openrouter" in call_text.lower()

    @pytest.mark.asyncio
    async def test_provider_command_invalid_provider(self):
        """Test /provider invalid shows error."""
        from agent.interfaces.telegram import provider_cmd
        
        # Mock update and context
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.username = "testuser"
        update.message = AsyncMock()
        
        context = MagicMock()
        context.args = ["invalid"]
        
        # Mock whitelist check
        with patch("agent.interfaces.telegram._is_user_allowed", return_value=True):
            await provider_cmd(update, context)
        
        # Should show error
        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        assert "Invalid" in call_text or "invalid" in call_text.lower()

    @pytest.mark.asyncio
    async def test_provider_unauthorized_user(self):
        """Test /provider denies unauthorized users."""
        from agent.interfaces.telegram import provider_cmd
        
        # Mock update and context
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.username = "unauthorized_user"
        update.message = AsyncMock()
        
        context = MagicMock()
        context.args = ["vllm"]
        
        with patch("agent.interfaces.telegram._is_user_allowed", return_value=False):
            await provider_cmd(update, context)
            
            # Should show access denied
            update.message.reply_text.assert_called_once()
            call_text = update.message.reply_text.call_args[0][0]
            assert "Access Denied" in call_text or "Denied" in call_text


class TestCLIProviderSwitching:
    """Tests for CLI --provider flag."""

    def test_cli_run_help_shows_provider(self):
        """Test that 'run --help' shows --provider option."""
        import subprocess
        import sys
        
        result = subprocess.run(
            [sys.executable, "-m", "agent", "run", "--help"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "--provider" in result.stdout or "-p" in result.stdout

    def test_cli_status_shows_default_provider(self):
        """Test that 'status' shows default provider."""
        import subprocess
        import sys
        
        result = subprocess.run(
            [sys.executable, "-m", "agent", "status"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "provider" in result.stdout.lower()


class TestProviderConfig:
    """Tests for provider configuration."""

    def test_default_provider_is_vllm(self):
        """Test that default provider is vLLM."""
        from agent.config import PROVIDER_DEFAULT
        
        assert PROVIDER_DEFAULT == "vllm"

    def test_vllm_base_url_default(self):
        """Test vLLM base URL default."""
        from agent.config import VLLM_BASE_URL
        
        assert "localhost:8000" in VLLM_BASE_URL

    def test_vllm_model_name_default(self):
        """Test vLLM model name default."""
        from agent.config import VLLM_MODEL_NAME
        
        assert "gpt-oss-120b" in VLLM_MODEL_NAME.lower()


class TestTaskInfoWithProvider:
    """Tests for TaskInfo with provider field."""

    def test_task_info_has_provider(self):
        """Test TaskInfo includes provider field."""
        from agent.interfaces.telegram import TaskInfo
        
        task = TaskInfo(
            task_text="test task",
            chat_id=123,
            provider="vllm",
        )
        
        assert task.provider == "vllm"

    def test_task_info_provider_optional(self):
        """Test TaskInfo provider is optional."""
        from agent.interfaces.telegram import TaskInfo
        
        task = TaskInfo(
            task_text="test task",
            chat_id=123,
        )
        
        assert task.provider is None
