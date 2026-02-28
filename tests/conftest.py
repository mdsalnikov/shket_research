"""Pytest configuration. Force exit after session so process does not hang.

Some plugins (e.g. from pydantic-ai deps) can leave background threads or
resources that prevent the interpreter from exiting after all tests pass.
"""

import os


def pytest_sessionfinish(session, exitstatus):
    """Exit process immediately after test session to avoid shutdown hang."""
    import sys

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exitstatus)
