"""Browser automation tool for headless web browsing.

This tool provides headless browser automation capabilities using Playwright.
It allows the agent to navigate websites, extract content, take screenshots,
and interact with web pages in a headless Ubuntu Server environment.

Features:
- Navigate to URLs and extract content
- Take screenshots of web pages
- Extract text from elements using CSS selectors
- Click on elements
- Fill form fields
- Get full page HTML

Usage:
    await browser_navigate("https://example.com")
    await browser_screenshot("/tmp/screenshot.png")
    await browser_get_text("h1")
    await browser_click("button")
    await browser_fill("input", "text")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Default timeout for browser operations (seconds)
DEFAULT_TIMEOUT = 30

# Browser instance cache (singleton pattern)
_browser_instance: Any = None
_page_instance: Any = None


async def _get_browser_page() -> Any:
    """Get or create browser page instance.
    
    Returns:
        Playwright Page instance
    
    Raises:
        RuntimeError: If browser cannot be launched
    """
    global _browser_instance, _page_instance
    
    if _page_instance and _browser_instance:
        # Check if page is still valid
        try:
            await _page_instance.evaluate("1")
            return _page_instance
        except Exception:
            # Page is invalid, recreate
            pass
    
    try:
        playwright = await async_playwright().start()
        _browser_instance = await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        _page_instance = await _browser_instance.new_page(
            viewport={"width": 1280, "height": 800}
        )
        return _page_instance
    except Exception as e:
        logger.error("Failed to launch browser: %s", e)
        raise RuntimeError(f"Failed to launch browser: {e}")


async def _close_browser() -> None:
    """Close browser instance."""
    global _browser_instance, _page_instance
    
    if _page_instance:
        try:
            await _page_instance.close()
        except Exception:
            pass
        _page_instance = None
    
    if _browser_instance:
        try:
            await _browser_instance.close()
        except Exception:
            pass
        _browser_instance = None


async def browser_navigate(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Navigate to a URL and return page content.
    
    Args:
        url: URL to navigate to
        timeout: Timeout in seconds (default: 30)
    
    Returns:
        Page title and summary of content
    
    Raises:
        ValueError: If URL is invalid
        RuntimeError: If navigation fails
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL: {url}. URL must start with http:// or https://")
    
    try:
        page = await _get_browser_page()
        
        logger.info("Navigating to: %s", url)
        await page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
        
        title = await page.title()
        content = await page.content()
        
        # Extract summary
        length = len(content)
        preview = content[:500] + "..." if length > 500 else content
        
        result = (
            f"✅ Successfully navigated to: {url}\n"
            f"📝 Title: {title}\n"
            f"📊 Content length: {length} chars\n"
            f"👁️ Preview:\n{preview}"
        )
        
        logger.info("Navigation successful: %s", title)
        return result
        
    except PlaywrightTimeoutError:
        error_msg = f"Timeout navigating to {url} after {timeout}s"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Failed to navigate to {url}: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


async def browser_screenshot(path: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Take a screenshot of the current page.
    
    Args:
        path: Path to save screenshot (PNG format)
        timeout: Timeout in seconds (default: 30)
    
    Returns:
        Confirmation message with path
    
    Raises:
        RuntimeError: If screenshot fails
    """
    try:
        page = await _get_browser_page()
        
        # Ensure path has .png extension
        if not path.lower().endswith(".png"):
            path = path + ".png"
        
        # Create directory if needed
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("Taking screenshot: %s", path)
        await page.screenshot(path=path, timeout=timeout * 1000)
        
        # Get file size
        file_size = Path(path).stat().st_size
        
        result = (
            f"✅ Screenshot saved to: {path}\n"
            f"📊 File size: {file_size:,} bytes"
        )
        
        logger.info("Screenshot saved: %s (%s bytes)", path, file_size)
        return result
        
    except Exception as e:
        error_msg = f"Failed to take screenshot: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


async def browser_get_text(selector: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Extract text from elements matching CSS selector.
    
    Args:
        selector: CSS selector
        timeout: Timeout in seconds (default: 30)
    
    Returns:
        Text content from matching elements
    
    Raises:
        RuntimeError: If no elements found or extraction fails
    """
    try:
        page = await _get_browser_page()
        
        logger.info("Extracting text from selector: %s", selector)
        
        # Try to get text from all matching elements
        elements = await page.query_selector_all(selector)
        
        if not elements:
            return f"⚠️ No elements found matching selector: {selector}"
        
        texts = []
        for i, element in enumerate(elements[:10]):  # Limit to 10 elements
            try:
                text = await element.inner_text()
                if text.strip():
                    texts.append(text.strip())
            except Exception:
                pass
        
        if not texts:
            return f"⚠️ No text found in elements matching: {selector}"
        
        result = (
            f"✅ Found {len(elements)} element(s) matching: {selector}\n"
            f"📝 Text content:\n" + "\n---\n".join(texts)
        )
        
        logger.info("Extracted %d element(s) from selector: %s", len(elements), selector)
        return result
        
    except Exception as e:
        error_msg = f"Failed to extract text from {selector}: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


async def browser_click(selector: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Click on an element matching CSS selector.
    
    Args:
        selector: CSS selector
        timeout: Timeout in seconds (default: 30)
    
    Returns:
        Confirmation message
    
    Raises:
        RuntimeError: If element not found or click fails
    """
    try:
        page = await _get_browser_page()
        
        logger.info("Clicking on selector: %s", selector)
        
        # Wait for element and click
        await page.click(selector, timeout=timeout * 1000)
        
        result = f"✅ Successfully clicked on element: {selector}"
        
        logger.info("Click successful: %s", selector)
        return result
        
    except Exception as e:
        error_msg = f"Failed to click on {selector}: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


async def browser_fill(selector: str, text: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Fill a form field with text.
    
    Args:
        selector: CSS selector for input field
        text: Text to fill
        timeout: Timeout in seconds (default: 30)
    
    Returns:
        Confirmation message
    
    Raises:
        RuntimeError: If element not found or fill fails
    """
    try:
        page = await _get_browser_page()
        
        logger.info("Filling selector %s with text: %s", selector, text[:50])
        
        # Clear and fill
        await page.fill(selector, text, timeout=timeout * 1000)
        
        result = f"✅ Successfully filled {selector} with: {text[:100]}{'...' if len(text) > 100 else ''}"
        
        logger.info("Fill successful: %s", selector)
        return result
        
    except Exception as e:
        error_msg = f"Failed to fill {selector}: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


async def browser_get_html(timeout: int = DEFAULT_TIMEOUT) -> str:
    """Get full page HTML.
    
    Args:
        timeout: Timeout in seconds (default: 30)
    
    Returns:
        Full page HTML content
    
    Raises:
        RuntimeError: If HTML extraction fails
    """
    try:
        page = await _get_browser_page()
        
        logger.info("Getting full page HTML")
        html = await page.content()
        
        length = len(html)
        preview = html[:1000] + "..." if length > 1000 else html
        
        result = (
            f"✅ Page HTML retrieved\n"
            f"📊 Length: {length} chars\n"
            f"👁️ Preview:\n{preview}"
        )
        
        logger.info("HTML retrieved: %d chars", length)
        return result
        
    except Exception as e:
        error_msg = f"Failed to get page HTML: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


async def browser_get_url() -> str:
    """Get current page URL.
    
    Returns:
        Current page URL
    
    Raises:
        RuntimeError: If URL cannot be retrieved
    """
    try:
        page = await _get_browser_page()
        url = page.url
        return f"🔗 Current URL: {url}"
    except Exception as e:
        error_msg = f"Failed to get current URL: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


async def browser_refresh(timeout: int = DEFAULT_TIMEOUT) -> str:
    """Refresh current page.
    
    Args:
        timeout: Timeout in seconds (default: 30)
    
    Returns:
        Confirmation message
    
    Raises:
        RuntimeError: If refresh fails
    """
    try:
        page = await _get_browser_page()
        
        logger.info("Refreshing page")
        await page.reload(wait_until="networkidle", timeout=timeout * 1000)
        
        url = page.url
        title = await page.title()
        
        result = f"✅ Page refreshed\n🔗 URL: {url}\n📝 Title: {title}"
        
        logger.info("Page refreshed: %s", title)
        return result
        
    except Exception as e:
        error_msg = f"Failed to refresh page: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
