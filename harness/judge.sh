#!/bin/zsh
# usage: judge.sh <task> <judge: fable|opus|gpt>  -> judge/<task>/vote-<judge>.json
B=.
T=$1; J=$2; D=$B/judge/$T
P="$(sed -n '1,/^$/p' $B/prompts/$T.txt | sed '/^$/d')"
Q="You are an impartial judge. Three anonymous submissions (A, B, C) were each produced in one shot from this exact prompt:

\"\"\"$P\"\"\"

The image sheet.jpg in the current directory shows each submission as one row labelled A, B, C. For animated or interactive results the row is a sequence of frames captured from the running page at even time intervals, left to right (interactive ones were played with the same scripted keyboard/mouse input). Open and look at sheet.jpg.

Judge only what you can see, on three criteria: (1) how well it fulfils the prompt, (2) visual quality and polish, (3) correctness - no visible bugs such as clipping, overflow, broken layout, or objects escaping. Rank all three from best to worst; no ties.

Reply with ONLY a JSON object, no markdown: {\"ranking\":[\"<best>\",\"<middle>\",\"<worst>\"],\"reasons\":{\"A\":\"...\",\"B\":\"...\",\"C\":\"...\"}} where each reason is one short Korean sentence."
cd $D
if [[ $J == gpt ]]; then
  env -i HOME=$HOME PATH=$PATH codex exec --skip-git-repo-check -s read-only -C . -m gpt-6.1-sol -c model_reasoning_effort=high -i sheet.jpg -o raw-$J.txt "$Q" < /dev/null > /dev/null 2>&1
else
  [[ $J == fable ]] && MODEL=claude-fable-5-2 || MODEL=claude-opus-5-5
  env -i HOME=$HOME PATH=$PATH USER=$USER claude -p "$Q" --model $MODEL --effort high --setting-sources "" --strict-mcp-config --allowedTools "Read" --output-format json 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('result',''))" > raw-$J.txt
fi
python3 - "$D" "$J" <<'PY'
import sys,json,re
d,j=sys.argv[1:3]; raw=open(f'{d}/raw-{j}.txt').read()
m=re.search(r'\{.*\}',raw,re.S); v=json.loads(m.group(0))
mp=json.load(open(f'{d}/mapping.json'))
v['models']=[mp[x] for x in v['ranking']]
json.dump(v,open(f'{d}/vote-{j}.json','w'),ensure_ascii=False,indent=1); print(d.split('/')[-1],j,v['ranking'],v['models'])
PY
