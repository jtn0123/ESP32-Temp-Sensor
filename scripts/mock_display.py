#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os

WIDTH, HEIGHT = 250, 122

def load_font(size: int):
    try:
        return ImageFont.truetype("Arial.ttf", size)
    except Exception:
        return ImageFont.load_default()

def draw_layout(draw: ImageDraw.ImageDraw, data: dict):
    # Regions
    INSIDE_TEMP = (6, 38, 124, 64)
    INSIDE_RH   = (6, 64, 124, 80)
    INSIDE_TIME = (6, 78, 124, 92)
    OUT_TEMP    = (131, 38, 220, 64)
    OUT_RH      = (131, 64, 220, 80)
    OUT_ICON    = (218, 22, 242, 46)
    STATUS      = (6, 96, 244, 118)

    # Header
    draw.rectangle([(0,0),(WIDTH-1,18)], fill=1, outline=0)
    font_hdr = load_font(12)
    draw.text((4,4), data.get("room_name","Room"), font=font_hdr, fill=0)

    # Section labels
    font_lbl = load_font(10)
    draw.text((6,22), "INSIDE", font=font_lbl, fill=0)
    draw.text((131,22), "OUTSIDE", font=font_lbl, fill=0)

    # Values
    font_big = load_font(14)
    font_sm = load_font(10)
    draw.text((INSIDE_TEMP[0], INSIDE_TEMP[1]), f"{data.get('inside_temp','72.5')}° F", font=font_big, fill=0)
    draw.text((INSIDE_RH[0], INSIDE_RH[1]), f"{data.get('inside_hum','47')}% RH", font=font_sm, fill=0)
    draw.text((INSIDE_TIME[0], INSIDE_TIME[1]), f"{data.get('time','10:32')}", font=font_sm, fill=0)

    draw.text((OUT_TEMP[0], OUT_TEMP[1]), f"{data.get('outside_temp','68.4')}° F", font=font_big, fill=0)
    draw.text((OUT_RH[0], OUT_RH[1]), f"{data.get('outside_hum','53')}% RH", font=font_sm, fill=0)
    # Icon placeholder box
    draw.rectangle([(OUT_ICON[0], OUT_ICON[1]), (OUT_ICON[2], OUT_ICON[3])], outline=0, width=1)
    draw.text((OUT_ICON[0]+1, OUT_ICON[1]+6), data.get('weather','Cloudy')[:4], font=font_sm, fill=0)

    # Status
    status_text = f"IP {data.get('ip','192.168.1.42')}  Batt {data.get('voltage','4.01')}V {data.get('percent','76')}%  ~{data.get('days','128')}d"
    draw.text((STATUS[0], STATUS[1]), status_text, font=font_sm, fill=0)

def main():
    img = Image.new('1', (WIDTH, HEIGHT), color=1)  # 1-bit, white background
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

if __name__ == "__main__":
    main()


