BIN ?= .venv/bin/

.PHONY: check
check:
	$(BIN)black --check .
	$(BIN)ruff check .
	$(BIN)mypy
	$(BIN)lint-imports
	$(BIN)pytest
