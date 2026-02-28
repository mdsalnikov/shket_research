"""Tests for progress tracking system."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from agent.progress import (
    ProgressTracker,
    ProgressState,
    ProgressUpdate,
    get_tracker,
    reset_tracker,
)


class TestProgressUpdate:
    """Test ProgressUpdate dataclass."""
    
    def test_progress_update_creation(self):
        """ProgressUpdate can be created with all fields."""
        update = ProgressUpdate(
            state=ProgressState.EXECUTING,
            step_number=2,
            total_steps=5,
            current_task="Testing code",
            todo_count=5,
            completed_count=2,
            message="Step 2 completed",
        )
        
        assert update.state == ProgressState.EXECUTING
        assert update.step_number == 2
        assert update.total_steps == 5
        assert update.current_task == "Testing code"
    
    def test_progress_update_to_string(self):
        """ProgressUpdate.to_string() creates readable output."""
        update = ProgressUpdate(
            state=ProgressState.EXECUTING,
            step_number=2,
            total_steps=5,
            current_task="Testing",
            todo_count=5,
            completed_count=2,
            message="Completed step 2",
        )
        
        result = update.to_string()
        
        assert "Progress Update" in result
        assert "EXECUTING" in result
        assert "2/5" in result
        assert "Testing" in result
    
    def test_progress_update_default_values(self):
        """ProgressUpdate has sensible defaults."""
        update = ProgressUpdate()
        
        assert update.state == ProgressState.IDLE
        assert update.step_number == 0
        assert update.todo_count == 0
        assert update.message == ""


class TestProgressTracker:
    """Test ProgressTracker class."""
    
    @pytest.fixture
    def tracker(self):
        """Create a tracker for testing."""
        reset_tracker()
        return ProgressTracker(chat_id=123, is_cli=True)
    
    @pytest.mark.asyncio
    async def test_start_task(self, tracker):
        """Tracker can start a task."""
        callback_called = False
        
        def cli_callback(msg):
            nonlocal callback_called
            callback_called = True
            assert "Starting task" in msg
        
        tracker.cli_callback = cli_callback
        
        await tracker.start_task("Test task")
        
        assert tracker.task_name == "Test task"
        assert tracker.state == ProgressState.PLANNING
        assert tracker.start_time is not None
        assert callback_called
    
    @pytest.mark.asyncio
    async def test_update_todo(self, tracker):
        """Tracker can update TODO status."""
        await tracker.start_task("Test task")
        
        callback_messages = []
        
        def cli_callback(msg):
            callback_messages.append(msg)
        
        tracker.cli_callback = cli_callback
        
        await tracker.update_todo(total_steps=5, completed_count=2, current_task="Step 2")
        
        assert tracker.total_steps == 5
        assert tracker.current_step == 2
        assert len(callback_messages) > 0
    
    @pytest.mark.asyncio
    async def test_set_state(self, tracker):
        """Tracker can change state."""
        await tracker.start_task("Test task")
        
        await tracker.set_state(ProgressState.EXECUTING, "Processing...")
        
        assert tracker.state == ProgressState.EXECUTING
    
    @pytest.mark.asyncio
    async def test_on_step_start(self, tracker):
        """Tracker can report step start."""
        await tracker.start_task("Test task")
        tracker.total_steps = 5
        
        messages = []
        
        def cli_callback(msg):
            messages.append(msg)
        
        tracker.cli_callback = cli_callback
        
        await tracker.on_step_start(1, "First step")
        
        assert len(messages) > 0
        assert any("Starting step 1" in msg for msg in messages)
    
    @pytest.mark.asyncio
    async def test_on_step_complete(self, tracker):
        """Tracker can report step completion."""
        await tracker.start_task("Test task")
        tracker.total_steps = 5
        
        messages = []
        
        def cli_callback(msg):
            messages.append(msg)
        
        tracker.cli_callback = cli_callback
        
        await tracker.on_step_complete(1, "First step", "Success")
        
        assert len(messages) > 0
        assert any("Step 1 completed" in msg for msg in messages)
    
    @pytest.mark.asyncio
    async def test_complete(self, tracker):
        """Tracker can mark task as complete."""
        await tracker.start_task("Test task")
        tracker.total_steps = 5
        tracker.completed_count = 5
        
        messages = []
        
        def cli_callback(msg):
            messages.append(msg)
        
        tracker.cli_callback = cli_callback
        
        await tracker.complete("All done!")
        
        assert tracker.state == ProgressState.COMPLETED
        assert tracker.end_time is not None
        assert len(messages) > 0
        # Check for completion message (case insensitive, partial match)
        assert any("completed" in msg.lower() or "all done" in msg.lower() for msg in messages)
    
    @pytest.mark.asyncio
    async def test_fail(self, tracker):
        """Tracker can mark task as failed."""
        await tracker.start_task("Test task")
        
        messages = []
        
        def cli_callback(msg):
            messages.append(msg)
        
        tracker.cli_callback = cli_callback
        
        await tracker.fail("Something went wrong")
        
        assert tracker.state == ProgressState.FAILED
        assert any("failed" in msg.lower() for msg in messages)
    
    def test_get_status(self, tracker):
        """Tracker can return status dict."""
        tracker.task_name = "Test"
        tracker.state = ProgressState.EXECUTING
        tracker.total_steps = 5
        tracker.completed_count = 2
        
        status = tracker.get_status()
        
        assert status["task"] == "Test"
        assert status["state"] == "EXECUTING"
        assert status["progress"] == "2/5"
    
    def test_format_duration(self, tracker):
        """Tracker formats duration correctly."""
        assert tracker._format_duration(30) == "30s"
        assert tracker._format_duration(90) == "1m 30s"
        assert tracker._format_duration(3661) == "1h 1m"


class TestTrackerGlobals:
    """Test global tracker management."""
    
    def test_get_tracker_creates_new(self):
        """get_tracker creates new tracker if none exists."""
        reset_tracker()
        
        tracker = get_tracker(chat_id=0, is_cli=True)
        
        assert tracker is not None
        assert tracker.chat_id == 0
        assert tracker.is_cli
    
    def test_get_tracker_returns_existing(self):
        """get_tracker returns existing tracker."""
        reset_tracker()
        
        tracker1 = get_tracker(chat_id=0, is_cli=True)
        tracker2 = get_tracker(chat_id=0, is_cli=True)
        
        assert tracker1 is tracker2
    
    def test_reset_tracker(self):
        """reset_tracker clears tracker."""
        reset_tracker()
        get_tracker(chat_id=0, is_cli=True)
        
        reset_tracker(chat_id=0, is_cli=True)
        
        # Should create new one after reset
        tracker = get_tracker(chat_id=0, is_cli=True)
        assert tracker is not None


class TestProgressTrackerTelegram:
    """Test ProgressTracker with Telegram callback."""
    
    @pytest.mark.asyncio
    async def test_telegram_callback(self):
        """Tracker sends updates to Telegram callback."""
        reset_tracker()
        
        callback_messages = []
        
        async def telegram_callback(chat_id, message):
            callback_messages.append((chat_id, message))
        
        tracker = ProgressTracker(
            chat_id=456,
            is_cli=False,
            telegram_callback=telegram_callback,
        )
        
        await tracker.start_task("Telegram task")
        await asyncio.sleep(0.1)  # Allow async callback to run
        
        assert len(callback_messages) > 0
        assert callback_messages[0][0] == 456
    
    @pytest.mark.asyncio
    async def test_telegram_callback_error_handling(self):
        """Tracker handles Telegram callback errors gracefully."""
        reset_tracker()
        
        async def failing_callback(chat_id, message):
            raise Exception("Telegram error")
        
        tracker = ProgressTracker(
            chat_id=456,
            is_cli=False,
            telegram_callback=failing_callback,
        )
        
        # Should not raise
        await tracker.start_task("Test task")
        await asyncio.sleep(0.1)


class TestProgressTrackerCLI:
    """Test ProgressTracker with CLI output."""
    
    @pytest.mark.asyncio
    async def test_cli_output_format(self):
        """CLI output includes progress bar and timestamp."""
        reset_tracker()
        
        output_lines = []
        
        def cli_callback(message):
            output_lines.append(message)
        
        tracker = ProgressTracker(chat_id=0, is_cli=True)
        tracker.cli_callback = cli_callback
        
        await tracker.start_task("CLI task")
        await tracker.update_todo(total_steps=3, completed_count=1)
        await asyncio.sleep(0.1)
        
        assert len(output_lines) > 0
        # Check for progress bar format
        assert any("[" in line and "]" in line for line in output_lines)
    
    @pytest.mark.asyncio
    async def test_cli_progress_bar(self):
        """CLI shows correct progress bar."""
        reset_tracker()
        
        output_lines = []
        
        def cli_callback(message):
            output_lines.append(message)
        
        tracker = ProgressTracker(chat_id=0, is_cli=True)
        tracker.cli_callback = cli_callback
        
        await tracker.start_task("Test")
        await tracker.update_todo(total_steps=5, completed_count=2)
        await asyncio.sleep(0.1)
        
        # Should show 2/5 progress
        assert any("2/5" in line for line in output_lines)
