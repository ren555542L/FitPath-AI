# FitPath Backend

## Running Tests

To run the test suite:
```bash
uv run pytest tests/
```

### Note on Warnings
If you run tests with `-W error` (e.g., `uv run pytest tests/ -W error`), the test suite will fail during collection due to unfixable third-party deprecation warnings. We have fixed all actionable warnings in our own codebase (e.g., Starlette/httpx deprecations and Pydantic V2 Config dicts).

The following unfixable warnings remain and are documented/ignored in `pyproject.toml`:
1. `DeprecationWarning: SelectableGroups dict interface is deprecated. Use select.` — This originates in Python 3.11+ `importlib.metadata` and is triggered by `opentelemetry/_importlib_metadata.py` (which is pulled in via `google.adk`'s telemetry stack). We cannot fix this without patching upstream libraries.
2. `BaseAgentConfig is deprecated` and `MCPTool class is deprecated` — These are internal migration warnings within `google.adk`. We are using the correct public API (`McpTool`, etc.).
3. `[EXPERIMENTAL] feature:` warnings — These are `UserWarning`s emitted by `google.adk` for features enabled internally by the framework.
