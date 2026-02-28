# Python Development

## Description
Expertise in Python programming, including modern Python 3.x features, 
best practices, debugging, and testing.

## When to Use
- User asks about Python code
- Need to write or debug Python scripts
- Python package management questions
- Async Python programming

## Tools
- `run_shell`: Execute Python scripts and commands
- `read_file`: Read Python source files
- `write_file`: Create or modify Python files
- `run_tests`: Run pytest test suites

## Patterns

### Virtual Environment Setup
Always use virtual environments for Python projects:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Testing Pattern
Write tests before or alongside code:
```python
def test_function():
    assert function(input) == expected
```

## Related Skills
- data_analysis
- testing
- bash
