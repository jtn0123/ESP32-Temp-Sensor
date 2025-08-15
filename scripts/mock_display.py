#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os
import hashlib

WIDTH, HEIGHT = 250, 122

def load_font(_size: int):
    # Use PIL's built-in font for deterministic rendering across environments
    return ImageFont.load_default()

def try_load_icon_png(weather: str):
    base = os.path.join('config','icons')
    key = (weather or '').strip().lower()
    candidates = [key, 'clear' if 'clear' in key or 'sun' in key else None,
                  'partly' if 'part' in key else None,
                  'cloudy' if 'cloud' in key else None,
                  'rain' if 'rain' in key else None,
                  'storm' if 'storm' in key or 'thunder' in key else None,
                  'snow' if 'snow' in key else None,
                  'fog' if 'fog' in key else None]
    for c in candidates:
        if not c: continue
        p = os.path.join(base, f'{c}.png')
        if os.path.exists(p):
            try:
                img = Image.open(p).convert('1')
                return img
            except Exception:
                continue
    return None

def draw_weather_icon(draw: ImageDraw.ImageDraw, box: tuple[int,int,int,int], weather: str):
    x0,y0,x1,y1 = box
    w = x1 - x0
    h = y1 - y0
    cx = x0 + w//2
    cy = y0 + h//2
    kind = (weather or '').strip().lower()
    icon = try_load_icon_png(kind)
    if icon is not None:
        iw, ih = icon.size
        # center paste
        px = x0 + (w - iw)//2
        py = y0 + (h - ih)//2
        draw.bitmap((px, py), icon, fill=0)
        return
    # simple vector icons for 1-bit display
    if 'sun' in kind or 'clear' in kind:
        r = min(w,h)//3
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=0, width=1)
        for dx,dy in [(0,-r-4),(0,r+4),(-r-4,0),(r+4,0),(-3,-3),(3,3),(-3,3),(3,-3)]:
            draw.line((cx,cy,cx+dx,cy+dy), fill=0, width=1)
    elif 'part' in kind:
        # sun peeking over cloud
        r = min(w,h)//4
        draw.ellipse((x0+4, y0+4, x0+4+2*r, y0+4+2*r), outline=0, width=1)
        draw.rounded_rectangle((x0+2, y0+h//2, x1-2, y1-4), radius=4, outline=0, width=1)
    elif 'cloud' in kind:
        draw.rounded_rectangle((x0+2, y0+8, x1-2, y1-4), radius=6, outline=0, width=1)
        draw.ellipse((x0+4, y0+2, x0+20, y0+18), outline=0, width=1)
        draw.ellipse((x0+14, y0, x0+30, y0+18), outline=0, width=1)
    elif 'rain' in kind:
        draw_weather_icon(draw, box, 'cloudy')
        for i in range(3):
            draw.line((x0+8+i*6, y0+18, x0+4+i*6, y0+26), fill=0, width=1)
    elif 'storm' in kind or 'thunder' in kind:
        draw_weather_icon(draw, box, 'cloudy')
        draw.line((cx-6, cy+6, cx, cy+2, cx-2, cy+10, cx+6, cy+6), fill=0, width=1)
    elif 'snow' in kind:
        draw_weather_icon(draw, box, 'cloudy')
        for i in range(2):
            xi = x0+8+i*8
            yi = y0+18
            draw.text((xi, yi), '*', font=load_font(8), fill=0)
    elif 'fog' in kind:
        for i in range(3):
            draw.line((x0+2, y0+8+i*6, x1-2, y0+8+i*6), fill=0, width=1)
    else:
        draw.rectangle([(x0,y0),(x1,y1)], outline=0, width=1)

def draw_layout(draw: ImageDraw.ImageDraw, data: dict):
    # Regions
    INSIDE_TEMP = (6, 38, 124, 64)
    INSIDE_RH   = (6, 64, 124, 80)
    INSIDE_TIME = (6, 78, 124, 92)
    OUT_TEMP    = (131, 38, 220, 64)
    OUT_RH      = (131, 64, 220, 80)
    OUT_ICON    = (218, 22, 242, 46)
    STATUS      = (6, 96, 244, 118)

    # Frame and header
    draw.rectangle([(0,0),(WIDTH-1,HEIGHT-1)], outline=0, width=1)
    draw.rectangle([(1,1),(WIDTH-2,18)], fill=1, outline=0)
    font_hdr = load_font(12)
    draw.text((4,4), data.get("room_name","Room"), font=font_hdr, fill=0)
    # Column separator
    draw.line((125,18,125,95), fill=0, width=1)
    # Header underline
    draw.line((1,18,WIDTH-2,18), fill=0, width=1)

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
    draw_weather_icon(draw, OUT_ICON, data.get('weather','Cloudy'))

    # Status
    status_text = f"IP {data.get('ip','192.168.1.42')}  Batt {data.get('voltage','4.01')}V {data.get('percent','76')}%  ~{data.get('days','128')}d"
    draw.text((STATUS[0], STATUS[1]), status_text, font=font_sm, fill=0)

def render(data: dict) -> Image.Image:
    img = Image.new('1', (WIDTH, HEIGHT), color=1)
    draw = ImageDraw.Draw(img)
    draw_layout(draw, data)
    return img

def image_md5(img: Image.Image) -> str:
    buf = img.tobytes()
    return hashlib.md5(buf).hexdigest()

def main():
    # 1-bit, white background
    img = Image.new('1', (WIDTH, HEIGHT), color=1)
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


