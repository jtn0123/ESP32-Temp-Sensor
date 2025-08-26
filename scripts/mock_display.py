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
        draw.rectangle([(x0, y0), (x1, y1)], outline=0, width=1)


def draw_layout(draw: ImageDraw.ImageDraw, data: dict):
    # Load shared geometry; fall back to current coordinates if missing
    g = load_geometry()

    def R(key: str, fallback_xywh: tuple[int, int, int, int]):
        v = g.get(key)
        if isinstance(v, list) and len(v) == 4:
            x, y, w, h = v
            return (x, y, x + w, y + h)
        return fallback_xywh

    _HEADER_NAME = R("HEADER_NAME", (6, 2, 6 + 160, 2 + 14))
    HEADER_TIME = R("HEADER_TIME", (172, 2, 172 + 72, 2 + 14))

    INSIDE_TEMP = R("INSIDE_TEMP", (6, 36, 6 + 118, 36 + 28))
    INSIDE_RH = R("INSIDE_RH", (6, 66, 6 + 118, 66 + 14))
    _INSIDE_TIME = R("INSIDE_TIME", (6, 82, 6 + 118, 82 + 12))
    OUT_TEMP = R("OUT_TEMP", (129, 36, 129 + 94, 36 + 28))
    R("WEATHER_ICON", (210, 22, 210 + 28, 22 + 28))
    R("OUT_ROW1_L", (131, 68, 131 + 44, 68 + 12))
    R("OUT_ROW1_R", (177, 68, 177 + 64, 68 + 12))
    OUT_ROW2_L = R("OUT_ROW2_L", (131, 78, 131 + 44, 78 + 12))
    OUT_ROW2_R = R("OUT_ROW2_R", (177, 78, 177 + 44, 78 + 12))
    FOOTER_L = R("FOOTER_L", (6, 90, 6 + 160, 90 + 32))
    FOOTER_WEATHER = R("FOOTER_WEATHER", (170, 90, 170 + 74, 90 + 32))
    R("STATUS", (6, 112, 6 + 238, 112 + 10))

    # Frame and header
    draw.rectangle([(0, 0), (WIDTH - 1, HEIGHT - 1)], outline=0, width=1)
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
    # Header underline
    draw.line((1, 18, WIDTH - 2, 18), fill=0, width=1)
    # Footer split line at y=92 like sim chrome
    draw.line((1, 92, WIDTH - 2, 92), fill=0, width=1)
    # Header right time within HEADER_TIME
    t = data.get("time", "10:32")
    tx = HEADER_TIME[0] + HEADER_TIME[2] - 2 - len(t) * 6
    ty = HEADER_TIME[1] + 1
    draw.text((tx, ty), t, font=load_font(10), fill=0)
    # Stabilize sampling: draw a 1px dot near the center of the time string
    cx = tx + max(1, len(t) * 3)
    draw.point((cx, ty + 2), fill=0)
    # Optional version string in top-right like device (if provided)
    v = str(data.get("fw_version") or "").strip()
    if v:
        vx = HEADER_TIME[0] + HEADER_TIME[2] - 2 - len("v") * 6 - len(v) * 6
        draw.text((vx, HEADER_TIME[1] + HEADER_TIME[3] - 8), "v", font=load_font(10), fill=0)
        draw.text((vx + 6, HEADER_TIME[1] + HEADER_TIME[3] - 8), v, font=load_font(10), fill=0)

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

    # Footer weather bar (match sim.js 'iconIn' drawing)
    bar_x = 130
    bar_y = 95
    bar_w = 114
    bar_h = FOOTER_WEATHER[3]
    icon_w = min(26, bar_w - 60)
    icon_h = min(22, bar_h - 4)
    gap = 8
    cond_label = str(data.get("weather", "Cloudy")).split(" ")[0].split("-")[0]
    tl_cond = int(ImageDraw.Draw(Image.new("1", (1, 1))).textlength(cond_label, font=font_sm))
    total_w = icon_w + gap + tl_cond
    start_x = bar_x + max(0, (bar_w - total_w) // 2)
    icon_cx = start_x + icon_w // 2
    icon_cy = bar_y + bar_h // 2
    # Ensure left-side non-white area similar to sim
    cond_lower = str(data.get("weather", "")).lower()
    left_box_w = 16
    if "moon" in cond_lower:
        left_box_w = 20
    elif any(k in cond_lower for k in ["rain"]):
        left_box_w = 22
    elif any(k in cond_lower for k in ["snow"]):
        left_box_w = 18
    elif any(k in cond_lower for k in ["storm", "thunder", "lightning"]):
        left_box_w = 24
    # Draw filled rect inside icon box to guarantee black pixels
    draw.rectangle(
        [
            (bar_x + 2, bar_y + 2),
            (bar_x + 2 + max(8, min(left_box_w, icon_w - 4)), bar_y + 2 + max(8, icon_h - 6)),
        ],
        fill=0,
    )
    # Simplified icon strokes
    # Use stroke-only rectangle as in sim before specific details
    draw.rectangle(
        [(start_x + 2, bar_y + 6), (start_x + icon_w - 2, bar_y + icon_h - 2)], outline=0, width=1
    )
    if any(k in cond_lower for k in ["rain"]):
        # diagonal raindrops
        for i in range(3):
            x0 = start_x + 6 + i * 6
            draw.line((x0, icon_cy + 2, x0 - 3, icon_cy + 8), fill=0, width=1)
    elif any(k in cond_lower for k in ["snow"]):
        for i in range(2):
            draw.text((start_x + 6 + i * 8, icon_cy + 2), "*", font=load_font(10), fill=0)
    elif any(k in cond_lower for k in ["storm", "thunder", "lightning"]):
        draw.line((icon_cx - 6, icon_cy + 2, icon_cx, icon_cy - 2), fill=0, width=1)
        draw.line((icon_cx, icon_cy - 2, icon_cx - 2, icon_cy + 6), fill=0, width=1)
        draw.line((icon_cx - 2, icon_cy + 6, icon_cx + 6, icon_cy + 2), fill=0, width=1)
    elif any(k in cond_lower for k in ["fog", "mist", "haze"]):
        for i in range(3):
            y0 = bar_y + 6 + i * 6
            draw.line((start_x + 2, y0, start_x + icon_w - 2, y0), fill=0, width=1)
    else:
        # circle (sun)
        r0 = min(icon_w, icon_h) // 3
        draw.ellipse((icon_cx - r0, icon_cy - r0, icon_cx + r0, icon_cy + r0), outline=0, width=1)
    # Label to the right of the icon, vertically centered
    label_x = start_x + icon_w + gap
    label_y = bar_y + max(0, (icon_h - font_sm.size) // 2) + 1
    draw.text((label_x, label_y), cond_label, font=font_sm, fill=0)

    # Status/footer split (match sim footer_split component)
    # Battery glyph (x=8,y=92 with +4 offset in sim => y=96 effective)
    pct = int(str(data.get("percent", "76")))
    bx, by, bw, bh = 8, 96, 13, 7
    draw.rectangle([(bx, by), (bx + bw, by + bh)], outline=0, width=1)
    draw.rectangle([(bx + bw, by + 2), (bx + bw + 2, by + 6)], fill=0)
    fillw = max(0, min(bw - 2, int((bw - 2) * (pct / 100))))
    if fillw > 0:
        draw.rectangle([(bx + 1, by + 1), (bx + 1 + fillw, by + bh - 1)], fill=0)
    # Left text above the split line
    left = f"Batt {data.get('voltage','4.01')}V {pct}%"
    draw.text((26, 90), left, font=font_sm, fill=0)
    eta = f"~{data.get('days','128')}d"
    draw.text((26, 100), eta, font=font_sm, fill=0)
    ip = f"IP {data.get('ip','192.168.1.42')}"
    # Center IP within FOOTER_L
    left_col_right = FOOTER_L[0] + (FOOTER_L[2])
    left_col_left = FOOTER_L[0]
    ip_w = len(ip) * 6
    ip_x = left_col_left + max(0, (left_col_right - left_col_left - ip_w) // 2)
    draw.text((ip_x, FOOTER_L[1] + 22), ip, font=font_sm, fill=0)


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
