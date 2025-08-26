PY=python3

.PHONY: test test-web browsers rebaseline lint lint-python lint-cpp lint-fix lint-all fw

test:
	$(PY) -m pytest

test-web: browsers
	$(PY) -m pytest tests/test_web_sim*.py

browsers:
	$(PY) -m pip install -q playwright || true
	$(PY) -m playwright install chromium

rebaseline:
	@echo "Rebaseline functionality temporarily disabled - use scripts directly"

lint: lint-python lint-cpp

lint-python:
	@echo "Running Python linters..."
	@python3 -m ruff check . --quiet
	@python3 -m mypy . --hide-error-context --no-color-output --ignore-missing-imports

lint-cpp:
	@echo "Running C++ linters..."
	@python3 -m cpplint firmware/arduino/src/*.{h,cpp}

lint-fix:
	@echo "Auto-fixing Python linting issues..."
	@python3 -m ruff check . --fix --unsafe-fixes
	@echo "✅ Python auto-fixes applied"

lint-all: lint
	@echo "🎉 All linters passed!"

fw:
	@echo "Building Arduino firmware"
	cd firmware/arduino && pio run -e feather_esp32s2_display_only -e feather_esp32s2_headless


