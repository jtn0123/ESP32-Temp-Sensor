#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os

SIZE = 24

def new_icon():
    img = Image.new('1', (SIZE, SIZE), color=1)
    return img, ImageDraw.Draw(img)

def save(img, name):
    out_dir = os.path.join('config','icons')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'{name}.png')
    img.save(path)
    print('wrote', path)

def sun():
    img, d = new_icon()
    cx,cy = SIZE//2, SIZE//2
    r = 7
    d.ellipse((cx-r,cy-r,cx+r,cy+r), outline=0, width=1)
    for dx,dy in [(0,-11),(0,11),(-11,0),(11,0),(-8,-8),(8,8),(-8,8),(8,-8)]:
        d.line((cx,cy,cx+dx,cy+dy), fill=0, width=1)
    return img

def cloudy():
    img, d = new_icon()
    d.rounded_rectangle((3,10,21,18), radius=5, outline=0, width=1)
    d.ellipse((4,6,12,14), outline=0, width=1)
    d.ellipse((10,5,18,13), outline=0, width=1)
    return img

def rain():
    img = cloudy()
    d = ImageDraw.Draw(img)
    for i in range(3):
        d.line((6+i*5,16,4+i*5,21), fill=0, width=1)
    return img

def storm():
    img = cloudy()
    d = ImageDraw.Draw(img)
    d.line((8,16,12,13,10,19,16,16), fill=0, width=1)
    return img

def snow():
    img = cloudy()
    d = ImageDraw.Draw(img)
    d.text((7,16), '*', fill=0)
    d.text((13,16), '*', fill=0)
    return img

def fog():
    img, d = new_icon()
    for i in range(3):
        d.line((3,8+i*5,21,8+i*5), fill=0, width=1)
    return img

def partly():
    img, d = new_icon()
    d.ellipse((2,2,12,12), outline=0, width=1)
    d.rounded_rectangle((5,11,21,18), radius=4, outline=0, width=1)
    return img

def main():
    mapping = {
        'clear': sun(),
        'sunny': sun(),
        'cloudy': cloudy(),
        'rain': rain(),
        'storm': storm(),
        'snow': snow(),
        'fog': fog(),
        'partly': partly(),
    }
    for name, img in mapping.items():
        save(img, name)

if __name__ == '__main__':
    main()


