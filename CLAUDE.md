@AGENTS.md

## Commands
- Build the package: `python -m build`
- Run the test suite: `pytest -q -p no:cacheprovider`
- Prefer a single test file while iterating: `pytest -q -p no:cacheprovider sec_mcp/tests/test_x.py`
- Full toolchain + env notes → `docs/agent-env.md`

## Claude-only
- Before running Python, check for an existing venv (`.venv/`, `venv/`) and activate it — or use `uv run`; never install into the system Python.
