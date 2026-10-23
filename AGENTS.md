# Frappe MCP fork

This is Newmatik's fork of `frappe-mcp`. Its public package and protocol
contracts are consumed by other Frappe applications. Preserve exported names,
registration behavior and response shapes during maintenance.

- Use the committed `uv.lock`: `uv sync --locked --python 3.13`.
- Run `uv run --locked ruff check .` and `uv run --locked pytest -q`.
  CI runs the offline suite on Python 3.10 and 3.13 with no site or credentials.
- The current lockfile's Pydantic native dependency does not build on Python
  3.14. Do not bypass its interpreter check; upgrading that dependency requires
  a separately tested change. Do not claim this gate validates a Frappe v16 bench.
- Keep tests independent of live Frappe sites and external services. Use
  synthetic inputs and mocks, and preserve the existing protocol tests.
- Never commit credentials, customer data or local configuration. This public
  fork uses Newmatik accounts only.
- Use focused Conventional Commits. `CLAUDE.md` points to these instructions.
