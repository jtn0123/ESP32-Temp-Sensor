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
	@echo "Rebaseline current Pillow major golden from scripts/mock_display.py"
	$(PY) - << 'PY'
import os, sys
sys.path.insert(0, os.path.join(os.getcwd(),'scripts'))
import PIL
import mock_display as md
data = {
  "room_name": "Office",
  "inside_temp": "72.5",
  "inside_hum": "47",
  "outside_temp": "68.4",
  "outside_hum": "53",
  "weather": "Cloudy",
  "time": "10:32",
  "ip": "192.168.1.42",
  "voltage": "4.01",
  "percent": "76",
  "days": "128",
}
img = md.render(data)
md5 = md.image_md5(img)
major = getattr(PIL, '__version__','0').split('.')[0]
p = os.path.join('tests', f'golden_default_pil{major}.md5')
with open(p,'w') as f: f.write(md5)
print('wrote', p, md5)
PY

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


