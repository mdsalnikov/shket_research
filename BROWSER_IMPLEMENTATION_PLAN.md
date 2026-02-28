# Browser Tool Implementation Plan

## 📋 Analysis

### Requirements from README
- Headless web browsing for Ubuntu Server (no GUI)
- Web search, page retrieval, form interaction, scraping
- Candidate: agent-browser by Vercel Labs (CLI tool in Rust)
- Must integrate with agent's tool-calling interface

### Research Findings

#### Option 1: agent-browser (Vercel Labs)
**Pros:**
- Built specifically for AI agents
- CLI-based (easy to call from shell)
- Rust-based (fast, reliable)
- Good for screenshots and snapshots

**Cons:**
- External dependency (need to install CLI)
- Limited Python API
- May need network access for npm/brew installation

#### Option 2: Playwright (Recommended)
**Pros:**
- Native Python library
- Excellent headless support
- Fast and reliable
- Good documentation
- Easy to install via pip
- Full programmatic control

**Cons:**
- Need to install browser binaries
- Slightly more complex API

#### Option 3: Selenium
**Pros:**
- Mature, well-documented
- Wide community support

**Cons:**
- Slower than Playwright
- More complex setup
- Older technology

### Decision: **Playwright**

**Why:**
1. Native Python integration (no external CLI needed)
2. Better control for agent use cases
3. Faster and more reliable than Selenium
4. Easy to install: `pip install playwright` + `playwright install`
5. Good for headless Ubuntu Server

---

## 🎯 Implementation Plan

### Phase 1: Core Browser Tool (This PR)

#### Features:
1. **navigate(url)** - Open URL and get page content
2. **screenshot(path)** - Take screenshot and save
3. **get_text(selector)** - Extract text from element
4. **click(selector)** - Click on element
5. **fill(selector, text)** - Fill form field
6. **get_html()** - Get full page HTML

#### Files to create:
- `agent/tools/browser.py` - Main browser tool
- `tests/test_browser.py` - Tests

#### Integration:
- Add to `agent/core/tools.py`
- Register in agent tool dispatcher
- Add to AGENTS.md documentation

### Phase 2: Advanced Features (Future)

- Wait for element/page load
- Handle JavaScript execution
- Cookie/session management
- Multi-tab support
- Form submission
- Scroll and interaction

---

## 📁 File Structure

```
agent/
├── tools/
│   ├── browser.py          # NEW: Browser automation tool
│   ├── shell.py
│   ├── filesystem.py
│   └── ...
├── core/
│   ├── tools.py            # Modified: Add browser tool
│   └── ...
tests/
├── test_browser.py         # NEW: Browser tool tests
└── ...
```

---

## 🔧 Technical Details

### Installation
```python
# In pyproject.toml dependencies
playwright = ">=1.40.0"

# After pip install, run:
playwright install  # Downloads browser binaries
```

### Tool Interface
```python
@tool
async def browser_navigate(url: str) -> str:
    """Navigate to URL and return page content."""
    pass

@tool
async def browser_screenshot(path: str) -> str:
    """Take screenshot and save to path."""
    pass

@tool
async def browser_get_text(selector: str) -> str:
    """Extract text from CSS selector."""
    pass
```

### Error Handling
- Timeout handling (30s default)
- Network error handling
- Invalid URL handling
- Selector not found handling

### Headless Mode
```python
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    # ... operations
    await browser.close()
```

---

## 🧪 Testing Strategy

### Unit Tests
- Mock browser for fast tests
- Test error handling
- Test parameter validation

### Integration Tests
- Real browser (optional, can be skipped in CI)
- Test actual navigation
- Test screenshot generation

### Test Cases
1. Navigate to valid URL
2. Navigate to invalid URL (error handling)
3. Take screenshot
4. Extract text from page
5. Click element
6. Fill form field
7. Timeout handling
8. Network error handling

---

## 📝 Implementation Steps

1. ✅ Research completed
2. ✅ Plan created
3. ⬜ Install playwright dependency
4. ⬜ Create browser.py tool
5. ⬜ Integrate with agent tools
6. ⬜ Write tests
7. ⬜ Test functionality
8. ⬜ Update documentation
9. ⬜ Git commit and push
10. ⬜ Create PR

---

## 🚀 Next Steps

**Immediate action:**
1. Add playwright to pyproject.toml
2. Create browser.py with basic navigation
3. Test with simple URL
4. Add more features iteratively

**Timeline:**
- Phase 1: 1-2 hours (basic functionality)
- Phase 2: Future sprint (advanced features)

---

## 📚 References

- [Playwright Python Docs](https://playwright.dev/python)
- [Vercel agent-browser](https://github.com/vercel-labs/agent-browser)
- [Headless Browser Automation Guide](https://www.browsercat.com/post/python-headless-browser-automation-guide)
