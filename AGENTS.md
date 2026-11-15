# Frappe MCP fork

This is Newmatik's fork of `frappe-mcp`. Its public package and protocol
contracts are consumed by other Frappe applications. Preserve exported names,
registration behavior and response shapes during maintenance.

- Use the committed `uv.lock`: `uv sync --locked --python 3.14` (the Frappe v16
  bench runs Python 3.14).
- Run `uv run --locked ruff check .` and `uv run --locked pytest -q`.
  CI runs the offline suite on Python 3.10, 3.13 and 3.14 with no site or
  credentials. Do not claim this gate validates a Frappe v16 bench.
- Keep the Pydantic range compatible with Frappe v16's pin (`pydantic~=2.12.5`)
  and every native dependency in the lock at a release with wheels for each
  interpreter in the CI matrix (check with `uv sync --locked --no-build`).
  Upgrade such a dependency in its own, separately tested change.
- Keep tests independent of live Frappe sites and external services. Use
  synthetic inputs and mocks, and preserve the existing protocol tests.
- Never commit credentials, customer data or local configuration. This public
  fork uses Newmatik accounts only.
- Use focused Conventional Commits. `CLAUDE.md` points to these instructions.
