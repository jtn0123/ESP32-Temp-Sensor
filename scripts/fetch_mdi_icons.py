#!/usr/bin/env python3
import os
import urllib.request

BASE = (
    "https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG/master/svg"
)

ICONS = [
    # Weather
    "weather-cloudy",
    "weather-sunny",
    "weather-partly-cloudy",
    "weather-fog",
    "weather-pouring",
    "weather-lightning",
    "weather-snowy",
    "weather-windy",
    "weather-windy-variant",
    "weather-night",
    "weather-night-partly-cloudy",
    # Moon phases
    "moon-new",
    "moon-waxing-crescent",
    "moon-first-quarter",
    "moon-waxing-gibbous",
    "moon-full",
    "moon-waning-gibbous",
    "moon-last-quarter",
    "moon-waning-crescent",
]


def fetch(name: str, out_dir: str) -> bool:
    url = f"{BASE}/{name}.svg"
    dst = os.path.join(out_dir, f"{name}.svg")
    try:
        with urllib.request.urlopen(url) as r:
            data = r.read()
        with open(dst, "wb") as f:
            f.write(data)
        print("fetched", name)
        return True
    except Exception as e:
        print("skip", name, e)
        return False


def main():
    out_dir = os.path.join("web", "icons", "mdi")
    os.makedirs(out_dir, exist_ok=True)
    ok = 0
    for name in ICONS:
        ok += 1 if fetch(name, out_dir) else 0
    print(f"done {ok}/{len(ICONS)}")


if __name__ == "__main__":
    main()
