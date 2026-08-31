# Contributing

Install the workspace with `uv sync --all-packages --group dev`.

Run focused tests with `uv run --frozen python -m pytest path/to/tests -q` and
the complete suite with `uv run --frozen python -m pytest -q`.
Quality checks are `uv run --frozen ruff check .`,
`uv run --frozen mypy packages`, and `git diff --check`.
Build packages with `uv build --all-packages`.
