#!/usr/bin/env python3
# usage: make_sheet.py <task> [n_frames]  -> judge/<task>/sheet.jpg + mapping.json (labels A/B/C shuffled, seeded by task)
import sys, os, json, random, subprocess
from PIL import Image, ImageDraw, ImageFont
B = '.'
task = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
models = ['fable', 'opus', 'gpt']
rnd = random.Random('fable52-' + task); order = models[:]; rnd.shuffle(order)
out = f'{B}/judge/{task}'; os.makedirs(out, exist_ok=True)
FW, FH = 640, 400
font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 64)
rows = []
for lab, m in zip('ABC', order):
    mp4 = f'{B}/rec/{task}-{m}.mp4'
    dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4]))
    static = task == 'svg'
    k = 1 if static else n
    row = Image.new('RGB', (110 + FW * n, FH), (20, 20, 20))
    for i in range(k):
        t = dur * (i + 0.5) / k
        tmp = f'{out}/_f.png'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{t:.2f}', '-i', mp4, '-frames:v', '1', '-vf', f'scale={FW*2 if static else FW}:{FH*2 if static else FH}', tmp], check=True)
        im = Image.open(tmp).convert('RGB')
        row.paste(im, (110 + FW * i, 0))
    if static:
        row = Image.new('RGB', (110 + FW * 2, FH * 2), (20, 20, 20)); row.paste(im, (110, 0))
    ImageDraw.Draw(row).text((28, row.height // 2 - 36), lab, fill=(255, 255, 255), font=font)
    rows.append(row)
W = max(r.width for r in rows); H = sum(r.height for r in rows) + 8 * 2
sheet = Image.new('RGB', (W, H), (0, 0, 0)); y = 0
for r in rows: sheet.paste(r, (0, y)); y += r.height + 8
if sheet.width > 2600: sheet = sheet.resize((2600, round(sheet.height * 2600 / sheet.width)), Image.LANCZOS)
sheet.save(f'{out}/sheet.jpg', quality=90)
json.dump(dict(zip('ABC', order)), open(f'{out}/mapping.json', 'w'))
os.remove(f'{out}/_f.png'); print(task, sheet.size)
