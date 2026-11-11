#!/usr/bin/env python3
"""Add the 4-model rematch (Gemini 4 Carbon joins) to ../site: carbon.json + copied results/recordings/sheets.
The 3-model page (index.html, data.json) is left as it was."""
import json, os, shutil, subprocess
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); O = os.path.join(os.path.dirname(S), 'site')
T = ['motion', 'physics', 'svg', 'three', 'game']; M = ['fable', 'opus', 'gpt', 'carbon']
old = json.load(open(f'{O}/data.json')); sc = json.load(open(f'{S}/judge4/scores.json'))
PRICE = {'in': 2.0, 'out': 10.0, 'cache': 0.10}
def usage(t):
    u = json.load(open(f'{S}/runs/{t}/carbon/log.json'))['usage']
    return eval(u) if isinstance(u, str) else u
def votes(d):
    out = []
    for j in M:
        v = json.load(open(f'{d}/vote-{j}.json'))
        mp = json.load(open(f'{os.path.dirname(d) if "v1-" in d else d}/mapping.json'))
        order = [mp[l] for l in v['ranking']]
        out.append({'judge': j, 'order': order, 'reasons': {mp[l]: v['reasons'][l] for l in v['reasons']}})
    return out
def pts(vs):
    p = {m: 0 for m in M}
    for v in vs:
        for i, m in enumerate(v['order']): p[m] += 4 - i
    return p
tasks = []; tot_cost = 0; tot_sec = 0
for t in T:
    o = next(x for x in old['tasks'] if x['id'] == t); ext = 'svg' if t == 'svg' else 'html'
    os.makedirs(f'{O}/results/{t}/carbon', exist_ok=True)
    src = f'{S}/runs/{t}/carbon/index.{ext}'; shutil.copy(src, f'{O}/results/{t}/carbon/index.{ext}')
    u = usage(t); cost = round(u['input_tokens'] * PRICE['in'] / 1e6 + u['output_tokens'] * PRICE['out'] / 1e6 + u['cache_read_tokens'] * PRICE['cache'] / 1e6, 2)
    secs = json.load(open(f'{S}/runs/{t}/carbon/meta.json'))['seconds']; tot_cost += u['input_tokens'] * PRICE['in'] / 1e6 + u['output_tokens'] * PRICE['out'] / 1e6 + u['cache_read_tokens'] * PRICE['cache'] / 1e6; tot_sec += secs
    res = {m: dict(o['results'][m]) for m in ['fable', 'opus', 'gpt']}
    c = {'file': f'results/{t}/carbon/index.{ext}', 'seconds': secs, 'bytes': os.path.getsize(src), 'cost_usd_est': cost,
         'tokens': {k: u[k] for k in ['input_tokens', 'output_tokens', 'cache_read_tokens']}}
    if t == 'svg':
        for m in M:
            shutil.copy(f'{S}/rec/svg-{m}.png', f'{O}/rec/svg4-{m}.png'); (res[m] if m != 'carbon' else c)['image'] = f'rec/svg4-{m}.png'
    else:
        dst = f'{O}/rec/{t}-carbon.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{S}/rec/{t}-carbon.mp4', '-vf', 'scale=960:-2', '-c:v', 'libx264', '-crf', '30', '-preset', 'slow', '-an', '-movflags', '+faststart', dst], check=True)
        c['video'] = f'rec/{t}-carbon.mp4'
    res['carbon'] = c
    vs = votes(f'{S}/judge4/{t}'); p = pts(vs); assert p == sc['rounds'][t], (t, p)
    os.makedirs(f'{O}/judge4', exist_ok=True); shutil.copy(f'{S}/judge4/{t}/sheet.jpg', f'{O}/judge4/{t}.jpg')
    row = {'id': t, 'name': o['name'], 'source': o['source'], 'url': o['url'], 'prompt': o['prompt'], 'suffix': o['suffix'],
           'mapping': json.load(open(f'{S}/judge4/{t}/mapping.json')), 'results': res, 'points': p,
           'points_3way': o['points'], 'sheet': f'judge4/{t}.jpg', 'votes': vs}
    tasks.append(row)
def first(tid, sub, name, note):
    row = next(x for x in tasks if x['id'] == tid); vs = votes(f'{S}/judge4/{tid}/{sub}')
    shutil.copy(f'{S}/judge4/{tid}/{sub}/sheet.jpg', f'{O}/judge4/{name}.jpg')
    row['correction'] = {'note': note, 'sheet': f'judge4/{name}.jpg', 'points': pts(vs), 'votes': vs}
first('svg', 'v1-mixed-capture', 'svg-v1-mixed-capture',
      '2026-11-11 정정: 처음 심사에 쓴 시트는 GPT-6.1 Sol과 Carbon의 그림은 칸에 꽉 차게, Fable 5.2와 Opus 5.5의 그림은 왼쪽 위에 작게 찍혀 있었습니다(캡처 방식이 달랐음). 네 장을 같은 방식(그림 전체를 칸에 맞춤)으로 다시 찍어 재심사했고, 위 점수는 재심사 결과입니다. 처음 받은 표는 아래에 그대로 둡니다.')
first('game', 'v1-black-start', 'game-v1-black-start',
      '2026-11-11 정정: Carbon 게임의 첫 녹화는 앞부분 몇 초가 까만 화면으로 찍혔습니다. 실제 창과 다시 한 녹화에서는 처음부터 정상으로 그려져, 녹화 쪽 문제로 판단했습니다. 같은 입력으로 다시 녹화해 재심사했고, 위 점수는 재심사 결과입니다. 처음 받은 표는 아래에 그대로 둡니다.')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{S}/judge4/game/v1-black-start/game-carbon-v1.mp4', '-vf', 'scale=960:-2', '-c:v', 'libx264', '-crf', '30', '-an', '-movflags', '+faststart', f'{O}/rec/game-carbon-v1-black-start.mp4'], check=True)
failed = {t: json.load(open(f'{S}/runs-failed-carbon-acceptedits/{t}/meta.json'))['seconds'] for t in ['motion', 'physics', 'three', 'game']}
data = {'date': '2026-11-11', 'models': {**old['models'], 'carbon': 'gemini-4-carbon'}, 'rule': sc['rule'], 'tasks': tasks,
        'total': sc['total'], 'total_excluding_self': sc['excluding_self']['total'], 'self_first_votes': sc['self_first_votes'], 'ballots': sc['ballots'],
        'total_3way': old['total'], 'seconds': {**old['seconds'], 'carbon': tot_sec}, 'cost_usd': {**old['cost_usd'], 'carbon_est': round(tot_cost, 2)},
        'carbon_price_per_mtok': {**PRICE, 'until': '2026-11-30', 'from_2026_12_01': {'in': 4.0, 'out': 20.0, 'cache': 0.20}, 'source': 'https://ai.google.dev/gemini-api/docs/pricing'},
        'carbon_first_attempt_empty_runs_seconds': failed}
assert data['total'] == {'fable': 61, 'opus': 47, 'gpt': 35, 'carbon': 57} and data['cost_usd']['carbon_est'] == 4.01 and tot_sec == 3229
json.dump(data, open(f'{O}/carbon.json', 'w'), ensure_ascii=False, indent=1)
for f in ['run_one.sh', 'scripts/judge4.sh', 'scripts/make_sheet4.py', 'scripts/svgfit.mjs', 'scripts/act-three-carbon.json', 'scripts/build_site4.py']:
    shutil.copy(f'{S}/{f}', f'{O}/harness/{os.path.basename(f)}')
print('ok', data['total'], data['seconds'], data['cost_usd'])
