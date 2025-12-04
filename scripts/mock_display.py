#!/usr/bin/env python3
import hashlib
import os

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 250, 122
# Optional layout identity exported from geometry JSON if present
LAYOUT_VERSION = 1
LAYOUT_CRC = ""


def load_font(_size: int):
    # Use PIL's built-in font for deterministic rendering across environments
    return ImageFont.load_default()


def load_geometry() -> dict:
    import json

    candidates = [
        os.path.join("config", "display_geometry.json"),
        os.path.join("web", "sim", "geometry.json"),
        os.path.join(os.path.dirname(__file__), "..", "web", "sim", "geometry.json"),
    ]
    for p in candidates:
        try:
            with open(p, "r") as f:
                data = json.load(f)
                # support both {rects:{...}} and flat {...}
                rects = data.get("rects", data)
                # Export layout identity if present for tests/tools
                try:
                    global LAYOUT_VERSION, LAYOUT_CRC
                    LAYOUT_VERSION = int(data.get("layout_version") or data.get("version") or 1)
                    LAYOUT_CRC = str(data.get("layout_crc") or "")
                except Exception:
                    pass
                return rects
        except Exception:
            continue
    return {}


def try_load_icon_png(weather: str):
    base = os.path.join("config", "icons")
    key = (weather or "").strip().lower()
    candidates = [
        key,
        "clear" if "clear" in key or "sun" in key else None,
        "partly" if "part" in key else None,
        "cloudy" if "cloud" in key else None,
        "rain" if "rain" in key else None,
        "storm" if "storm" in key or "thunder" in key else None,
        "snow" if "snow" in key else None,
        "fog" if "fog" in key else None,
    ]
    for c in candidates:
        if not c:
            continue
        p = os.path.join(base, f"{c}.png")
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("1")
                return img
            except Exception:
                continue
    return None


def draw_weather_icon(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], weather: str):
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    cx = x0 + w // 2
    cy = y0 + h // 2
    kind = (weather or "").strip().lower()
    icon = try_load_icon_png(kind)
    if icon is not None:
        iw, ih = icon.size
        # center paste
        px = x0 + (w - iw) // 2
        py = y0 + (h - ih) // 2
        draw.bitmap((px, py), icon, fill=0)
        return
    # simple vector icons for 1-bit display
    if "sun" in kind or "clear" in kind:
        r = min(w, h) // 3
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=0, width=1)
        for dx, dy in [
            (0, -r - 4),
            (0, r + 4),
            (-r - 4, 0),
            (r + 4, 0),
            (-3, -3),
            (3, 3),
            (-3, 3),
            (3, -3),
        ]:
            draw.line((cx, cy, cx + dx, cy + dy), fill=0, width=1)
    elif "part" in kind:
        # sun peeking over cloud
        r = min(w, h) // 4
        draw.ellipse((x0 + 4, y0 + 4, x0 + 4 + 2 * r, y0 + 4 + 2 * r), outline=0, width=1)
        draw.rounded_rectangle((x0 + 2, y0 + h // 2, x1 - 2, y1 - 4), radius=4, outline=0, width=1)
    elif "cloud" in kind:
        draw.rounded_rectangle((x0 + 2, y0 + 8, x1 - 2, y1 - 4), radius=6, outline=0, width=1)
        draw.ellipse((x0 + 4, y0 + 2, x0 + 20, y0 + 18), outline=0, width=1)
        draw.ellipse((x0 + 14, y0, x0 + 30, y0 + 18), outline=0, width=1)
    elif "rain" in kind:
        draw_weather_icon(draw, box, "cloudy")
        for i in range(3):
            draw.line((x0 + 8 + i * 6, y0 + 18, x0 + 4 + i * 6, y0 + 26), fill=0, width=1)
    elif "storm" in kind or "thunder" in kind:
        draw_weather_icon(draw, box, "cloudy")
        draw.line((cx - 6, cy + 6, cx, cy + 2, cx - 2, cy + 10, cx + 6, cy + 6), fill=0, width=1)
    elif "snow" in kind:
        draw_weather_icon(draw, box, "cloudy")
        for i in range(2):
            xi = x0 + 8 + i * 8
            yi = y0 + 18
            draw.text((xi, yi), "*", font=load_font(8), fill=0)
    elif "fog" in kind:
        for i in range(3):
            draw.line((x0 + 2, y0 + 8 + i * 6, x1 - 2, y0 + 8 + i * 6), fill=0, width=1)
    else:
        draw.rectangle(((x0, y0), (x1, y1)), outline=0, width=1)


def draw_layout(draw: ImageDraw.ImageDraw, data: dict):
    # Load shared geometry; fall back to current coordinates if missing
    g = load_geometry()

    def R(key: str, fallback_xywh: tuple[int, int, int, int]):
        v = g.get(key)
        if isinstance(v, list) and len(v) == 4:
            x, y, w, h = v
            return (x, y, x + w, y + h)
        return fallback_xywh

    # Fallback coords updated to match ui_spec.json (format: x, y, x+w, y+h)
    _HEADER_NAME = R("HEADER_NAME", (6, 2, 6 + 90, 2 + 14))
    # Use HEADER_TIME_CENTER (current layout) with correct fallback coords
    HEADER_TIME = R("HEADER_TIME_CENTER", (100, 2, 100 + 50, 2 + 14))

    # Updated to match current geometry: y=34, h=26
    INSIDE_TEMP = R("INSIDE_TEMP", (6, 34, 6 + 118, 34 + 26))
    # Renamed from INSIDE_RH, updated coords: y=60, h=10
    INSIDE_RH = R("INSIDE_HUMIDITY", (6, 60, 6 + 118, 60 + 10))
    # Renamed from INSIDE_TIME to INSIDE_PRESSURE: y=70, h=10
    _INSIDE_PRESSURE = R("INSIDE_PRESSURE", (6, 70, 6 + 118, 70 + 10))
    OUT_TEMP = R("OUT_TEMP", (129, 36, 129 + 94, 36 + 28))
    # Updated coords: x=168, y=90, w=30, h=32
    R("WEATHER_ICON", (168, 90, 168 + 30, 90 + 32))
    # OUT_PRESSURE: x=177, y=68, w=64, h=12
    R("OUT_PRESSURE", (177, 68, 177 + 64, 68 + 12))
    # OUT_HUMIDITY: x=131, y=78, w=44, h=12 (alias OUT_ROW2_L for backward compat)
    OUT_ROW2_L = R("OUT_HUMIDITY", (131, 78, 131 + 44, 78 + 12))
    # OUT_WIND: x=177, y=80, w=44, h=10 (alias OUT_ROW2_R for backward compat)
    OUT_ROW2_R = R("OUT_WIND", (177, 80, 177 + 44, 80 + 10))
    # FOOTER_STATUS (alias FOOTER_L for backward compat)
    FOOTER_L = R("FOOTER_STATUS", (6, 90, 6 + 160, 90 + 32))
    # Updated coords: x=200, y=90, w=44, h=32
    FOOTER_WEATHER = R("FOOTER_WEATHER", (200, 90, 200 + 44, 90 + 32))

    # Frame and header
    draw.rectangle(((0, 0), (WIDTH - 1, HEIGHT - 1)), outline=0, width=1)
    font_hdr = load_font(12)
    # Header room name inside HEADER_NAME rect with 1px inset like sim text op
    draw.text(
        ((_HEADER_NAME[0] + 1), (_HEADER_NAME[1] + 1)),
        data.get("room_name", "Room"),
        font=font_hdr,
        fill=0,
    )
    # Header rules
    # Column separator
    draw.line((125, 18, 125, 121), fill=0, width=1)
    # Header underline - x extends to 249 per ui_spec.json
    draw.line((1, 18, WIDTH - 1, 18), fill=0, width=1)
    # Footer split line at y=84 to match ui_spec.json chrome (1,84) to (249,84)
    draw.line((1, 84, WIDTH - 1, 84), fill=0, width=1)
    # Header right time within HEADER_TIME
    t = data.get("time", "10:32")
    # HEADER_TIME is (x0, y0, x1, y1) - use x1 (right edge) for right-aligned text
    tx = HEADER_TIME[2] - 2 - len(t) * 6
    ty = HEADER_TIME[1] + 1
    draw.text((tx, ty), t, font=load_font(10), fill=0)
    # Stabilize sampling: draw a 1px dot near the center of the time string
    cx = tx + max(1, len(t) * 3)
    draw.point((cx, ty + 2), fill=0)
    # Optional version string in top-right like device (if provided)
    v = str(data.get("fw_version") or "").strip()
    if v:
        # Use x1 (right edge) for right-aligned positioning, same Y as time
        vx = HEADER_TIME[2] - 2 - len("v") * 6 - len(v) * 6
        draw.text((vx, ty), "v", font=load_font(10), fill=0)
        draw.text((vx + 6, ty), v, font=load_font(10), fill=0)

    # Section labels centered above temp rects
    font_lbl = load_font(10)

    def center_label(rect, text):
        x0, y0, x1, y1 = rect
        w = x1 - x0
        tl = int(ImageDraw.Draw(Image.new("1", (1, 1))).textlength(text, font=font_lbl))
        lx = x0 + max(0, (w - tl) // 2)
        draw.text((lx, 22), text, font=font_lbl, fill=0)

    center_label(INSIDE_TEMP, "INSIDE")
    center_label(OUT_TEMP, "OUTSIDE")

    # Values
    font_big = load_font(14)
    font_sm = load_font(10)

    # helpers for right-aligned temps using default font metrics
    def draw_temp_right(rect, value_str: str):
        x0, y0, x1, y1 = rect
        units_w = 14
        units_left = x1 - units_w
        num_right = units_left - 2
        s = str(value_str or "")

        # drop fractional first, then truncate from right
        def text_w(st: str) -> int:
            return int(ImageDraw.Draw(Image.new("1", (1, 1))).textlength(st, font=font_big))

        while len(s) > 1 and (x0 + text_w(s)) > num_right:
            if "." in s:
                s = s.split(".", 1)[0]
            else:
                s = s[:-1]
        num_w = text_w(s)
        draw.text((num_right - num_w, y0), s, font=font_big, fill=0)
        draw.text((units_left + 2, y0 + 2), "°", font=load_font(10), fill=0)
        draw.text((units_left + 8, y0 + 2), "F", font=load_font(10), fill=0)

    draw_temp_right(INSIDE_TEMP, str(data.get("inside_temp", "72.5")))
    inside_rh_text = f"{data.get('inside_hum','47')}% RH"
    draw.text((INSIDE_RH[0], INSIDE_RH[1]), inside_rh_text, font=font_sm, fill=0)

    draw_temp_right(OUT_TEMP, str(data.get("outside_temp", "68.4")))
    # Bottom small rows per spec: RH left bottom, wind right bottom
    outside_rh_text = f"{data.get('outside_hum','53')}% RH"
    draw.text((OUT_ROW2_L[0], OUT_ROW2_L[1]), outside_rh_text, font=font_sm, fill=0)
    try:
        wind_mps = float(data.get("wind", "4.2"))
    except Exception:
        wind_mps = 4.2
    wind_text = f"{wind_mps*2.237:.1f} mph"
    draw.text((OUT_ROW2_R[0], OUT_ROW2_R[1]), wind_text, font=font_sm, fill=0)

    # Weather icon in WEATHER_ICON region [168, 90, 30, 32]
    # Weather text in FOOTER_WEATHER region [200, 90, 44, 32]
    # These match the firmware display_renderer.cpp and ui_spec.json
    icon_x, icon_y, icon_w, icon_h = 168, 90, 30, 32
    weather_x, weather_y, weather_w, weather_h = 200, 90, 44, 32
    
    cond_label = str(data.get("weather", "Cloudy")).split(" ")[0].split("-")[0]
    cond_lower = str(data.get("weather", "")).lower()
    
    # Draw weather icon centered in WEATHER_ICON region
    icon_cx = icon_x + icon_w // 2
    icon_cy = icon_y + icon_h // 2
    
    # Simple icon rendering
    if any(k in cond_lower for k in ["rain", "shower"]):
        # cloud with rain drops
        draw.rounded_rectangle((icon_x + 2, icon_y + 8, icon_x + icon_w - 2, icon_y + 20), radius=4, outline=0, width=1)
        for i in range(3):
            x0 = icon_x + 8 + i * 6
            draw.line((x0, icon_y + 22, x0 - 2, icon_y + 28), fill=0, width=1)
    elif any(k in cond_lower for k in ["snow"]):
        draw.rounded_rectangle((icon_x + 2, icon_y + 8, icon_x + icon_w - 2, icon_y + 20), radius=4, outline=0, width=1)
        for i in range(2):
            draw.text((icon_x + 6 + i * 10, icon_y + 20), "*", font=load_font(10), fill=0)
    elif any(k in cond_lower for k in ["storm", "thunder", "lightning"]):
        draw.rounded_rectangle((icon_x + 2, icon_y + 6, icon_x + icon_w - 2, icon_y + 18), radius=4, outline=0, width=1)
        draw.line((icon_cx - 4, icon_cy + 4, icon_cx + 2, icon_cy), fill=0, width=1)
        draw.line((icon_cx + 2, icon_cy, icon_cx - 2, icon_cy + 8), fill=0, width=1)
    elif any(k in cond_lower for k in ["fog", "mist", "haze"]):
        for i in range(3):
            y0 = icon_y + 10 + i * 6
            draw.line((icon_x + 4, y0, icon_x + icon_w - 4, y0), fill=0, width=1)
    elif any(k in cond_lower for k in ["cloud", "overcast"]):
        draw.rounded_rectangle((icon_x + 2, icon_y + 10, icon_x + icon_w - 2, icon_y + 24), radius=6, outline=0, width=1)
    elif any(k in cond_lower for k in ["sun", "clear"]):
        r0 = min(icon_w, icon_h) // 4
        draw.ellipse((icon_cx - r0, icon_cy - r0, icon_cx + r0, icon_cy + r0), outline=0, width=1)
    else:
        # Default: simple circle
        r0 = min(icon_w, icon_h) // 4
        draw.ellipse((icon_cx - r0, icon_cy - r0, icon_cx + r0, icon_cy + r0), outline=0, width=1)
    
    # Draw weather text centered in FOOTER_WEATHER region at y=109
    tl_cond = int(ImageDraw.Draw(Image.new("1", (1, 1))).textlength(cond_label, font=font_sm))
    text_x = weather_x + max(0, (weather_w - tl_cond) // 2)
    text_y = weather_y + 19  # y=90+19=109, matches firmware
    draw.text((text_x, text_y), cond_label, font=font_sm, fill=0)

    # Status/footer split (match firmware draw_status_line_direct layout)
    # 3-row stacked layout:
    # Row 1: Battery glyph + voltage/percent at y=87
    # Row 2: Days remaining at y=98
    # Row 3: IP centered at y=109
    pct = int(str(data.get("percent", "76")))
    bx, by, bw, bh = 8, 87, 13, 7
    draw.rectangle(((bx, by), (bx + bw, by + bh)), outline=0, width=1)
    draw.rectangle(((bx + bw, by + 2), (bx + bw + 2, by + 6)), fill=0)
    fillw = max(0, min(bw - 2, int((bw - 2) * (pct / 100))))
    if fillw > 0:
        draw.rectangle(((bx + 1, by + 1), (bx + 1 + fillw, by + bh - 1)), fill=0)
    # Row 1: Battery text next to icon
    left = f"{data.get('voltage','4.01')}V {pct}%"
    draw.text((27, 87), left, font=font_sm, fill=0)
    # Row 2: Days remaining
    eta = f"~{data.get('days','128')}d"
    draw.text((8, 98), eta, font=font_sm, fill=0)
    # Row 3: IP centered in FOOTER_STATUS region
    ip_val = data.get('ip', '192.168.1.42')
    if ip_val and ip_val != "0.0.0.0":
        ip = f"IP {ip_val}"
    else:
        ip = "IP --"
    # Center IP within FOOTER_L
    left_col_width = FOOTER_L[2] - FOOTER_L[0]
    ip_w = len(ip) * 6
    ip_x = FOOTER_L[0] + max(0, (left_col_width - ip_w) // 2)
    draw.text((ip_x, 109), ip, font=font_sm, fill=0)


def render(data: dict) -> Image.Image:
    img = Image.new("1", (WIDTH, HEIGHT), color=1)
    draw = ImageDraw.Draw(img)
    draw_layout(draw, data)
    return img


def image_md5(img: Image.Image) -> str:
    buf = img.tobytes()
    return hashlib.md5(buf).hexdigest()


def main():
    # 1-bit, white background
    img = Image.new("1", (WIDTH, HEIGHT), color=1)
    draw = ImageDraw.Draw(img)
    sample = {
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
    draw_layout(draw, sample)

    out_dir = os.path.join("out")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "display_mock.png")
    img.save(out_path)
    print(f"Wrote {out_path}")
    # Also save a canonical expected image name for CI artifact collection
    out_expected = os.path.join(out_dir, "expected.png")
    try:
        img.save(out_expected)
        print(f"Wrote {out_expected}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
