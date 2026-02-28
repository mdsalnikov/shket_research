# CI and PR merge policy

## Workflow

- **File:** `.github/workflows/ci.yml`
- **Runs on:** push and pull_request to `main`
- **Jobs:**
  - **lint:** `ruff check .` and `ruff format --check .`
  - **test:** `pytest tests/ -m "not agent" --ignore=tests/test_resumable_tasks.py -v --tb=short`
    - Excludes tests that require LLM (marker `agent`) and the broken-import `test_resumable_tasks`.

## Branch protection

1. GitHub → **Settings** → **Branches** → **Add rule** for `main`.
2. Enable **Require status checks to pass before merging**.
3. Select the **CI** workflow (both `lint` and `test` jobs).
4. Save. PRs cannot be merged until CI is green.

## If CI fails — Shket fixes the PR

Do not merge until tests pass.

1. Run the agent (Telegram, CLI, or cron) with a task like:  
   *"Fix the CI failures on the current branch. Run locally: `pytest tests/ -m 'not agent' --ignore=tests/test_resumable_tasks.py` and `ruff check .`. Fix the code, commit, push to this branch. Repeat until CI is green. Only after CI passes, merge the PR and restart the bot."*
2. The agent uses `run_tests`, `run_shell` (ruff), `read_file`/`write_file`, `git_add`/`git_commit`/`git_push`.
3. When CI is green, merge the PR (e.g. `run_gh("pr merge <number>")` or GitHub UI), then restart the bot (e.g. `RESTART_CMD` or manual).

Self-repair cron (`python -m agent self-repair-check`) creates a branch and PR; if that PR’s CI fails, run the agent to fix that branch, push, wait for green CI, then merge and restart.
