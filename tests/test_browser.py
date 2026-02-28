"""Tests for browser automation tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.tools.browser import (
    browser_navigate,
    browser_screenshot,
    browser_get_text,
    browser_click,
    browser_fill,
    browser_get_html,
    browser_get_url,
    browser_refresh,
    _close_browser,
    _browser_instance,
    _page_instance,
)


@pytest.fixture(autouse=True)
def reset_browser_state():
    """Reset browser state before each test."""
    global _browser_instance, _page_instance
    from agent.tools import browser
    browser._browser_instance = None
    browser._page_instance = None
    yield
    browser._browser_instance = None
    browser._page_instance = None


class TestBrowserNavigate:
    """Test browser_navigate function."""
    
    @pytest.mark.asyncio
    async def test_navigate_success(self):
        """Test successful navigation to a URL."""
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        mock_page.goto = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        
        with patch("agent.tools.browser.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            result = await browser_navigate("https://example.com")
            
            assert "Successfully navigated" in result
            assert "Test Page" in result
            assert "https://example.com" in result
    
    @pytest.mark.asyncio
    async def test_navigate_invalid_url(self):
        """Test navigation with invalid URL."""
        with pytest.raises(ValueError, match="Invalid URL"):
            await browser_navigate("not-a-url")
    
    @pytest.mark.asyncio
    async def test_navigate_without_protocol(self):
        """Test navigation without http/https protocol."""
        with pytest.raises(ValueError, match="Invalid URL"):
            await browser_navigate("example.com")


class TestBrowserScreenshot:
    """Test browser_screenshot function."""
    
    @pytest.mark.asyncio
    async def test_screenshot_success(self):
        """Test successful screenshot."""
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_page.screenshot = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        
        with patch("agent.tools.browser.async_playwright") as mock_async_pw, \
             patch("agent.tools.browser.Path") as mock_path:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            mock_stat = MagicMock()
            mock_stat.st_size = 1024
            mock_path_instance = MagicMock()
            mock_path_instance.stat = MagicMock(return_value=mock_stat)
            mock_path.return_value = mock_path_instance
            
            result = await browser_screenshot("/tmp/test.png")
            
            assert "Screenshot saved" in result
            assert "/tmp/test.png" in result
    
    @pytest.mark.asyncio
    async def test_screenshot_adds_png_extension(self):
        """Test that .png extension is added if missing."""
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_page.screenshot = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        
        with patch("agent.tools.browser.async_playwright") as mock_async_pw, \
             patch("agent.tools.browser.Path") as mock_path:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            mock_stat = MagicMock()
            mock_stat.st_size = 1024
            mock_path_instance = MagicMock()
            mock_path_instance.stat = MagicMock(return_value=mock_stat)
            mock_path.return_value = mock_path_instance
            
            result = await browser_screenshot("/tmp/test")
            
            assert ".png" in result


class TestBrowserGetText:
    """Test browser_get_text function."""
    
    @pytest.mark.asyncio
    async def test_get_text_success(self):
        """Test successful text extraction."""
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_element = AsyncMock()
        mock_element.inner_text = AsyncMock(return_value="Test text")
        mock_page.query_selector_all = AsyncMock(return_value=[mock_element])
        
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        
        with patch("agent.tools.browser.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            result = await browser_get_text("h1")
            
            assert "Found" in result
            assert "Test text" in result
    
    @pytest.mark.asyncio
    async def test_get_text_no_elements(self):
        """Test text extraction when no elements found."""
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_page.query_selector_all = AsyncMock(return_value=[])
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        
        with patch("agent.tools.browser.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            result = await browser_get_text(".nonexistent")
            
            assert "No elements found" in result


class TestBrowserClick:
    """Test browser_click function."""
    
    @pytest.mark.asyncio
    async def test_click_success(self):
        """Test successful click."""
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_page.click = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        
        with patch("agent.tools.browser.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            result = await browser_click("button")
            
            assert "Successfully clicked" in result
            assert "button" in result


class TestBrowserFill:
    """Test browser_fill function."""
    
    @pytest.mark.asyncio
    async def test_fill_success(self):
        """Test successful form fill."""
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_page.fill = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        
        with patch("agent.tools.browser.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            result = await browser_fill("input", "test value")
            
            assert "Successfully filled" in result
            assert "test value" in result


class TestBrowserGetUrl:
    """Test browser_get_url function."""
    
    @pytest.mark.asyncio
    async def test_get_url_success(self):
        """Test successful URL retrieval."""
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_page.url = "https://example.com/page"
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        
        with patch("agent.tools.browser.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            result = await browser_get_url()
            
            assert "Current URL" in result
            assert "https://example.com/page" in result


class TestBrowserRefresh:
    """Test browser_refresh function."""
    
    @pytest.mark.asyncio
    async def test_refresh_success(self):
        """Test successful page refresh."""
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_page.reload = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Refreshed Page")
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        
        with patch("agent.tools.browser.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            result = await browser_refresh()
            
            assert "Page refreshed" in result


class TestBrowserHelpers:
    """Test browser helper functions."""
    
    @pytest.mark.asyncio
    async def test_close_browser(self):
        """Test browser cleanup."""
        await _close_browser()
        # Should not raise


class TestBrowserIntegration:
    """Integration tests for browser tool."""
    
    @pytest.mark.asyncio
    async def test_multiple_operations(self):
        """Test multiple browser operations in sequence."""
        mock_playwright_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_page.title = AsyncMock(return_value="Test")
        mock_page.content = AsyncMock(return_value="<html></html>")
        mock_page.goto = AsyncMock()
        mock_page.url = "https://example.com"
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        
        with patch("agent.tools.browser.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            # Navigate
            result1 = await browser_navigate("https://example.com")
            assert "Successfully navigated" in result1
            
            # Get URL
            result2 = await browser_get_url()
            assert "Current URL" in result2
            
            # Should reuse same page instance
            assert mock_browser.new_page.call_count == 1
