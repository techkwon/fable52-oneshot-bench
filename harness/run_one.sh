#!/bin/zsh
# usage: run_one.sh <model: fable|opus|gpt> <task>
M=$1; T=$2
BASE=.
WORK="$3/$T/$M"; mkdir -p "$WORK"; cd "$WORK"
PROMPT="$(cat $BASE/prompts/$T.txt)"
START=$(date +%s)
case $M in
  fable) MODEL=claude-fable-5-2;;
  opus)  MODEL=claude-opus-5-5;;
esac
if [[ $M == gpt ]]; then
  env -i HOME=$HOME PATH=$PATH codex exec --skip-git-repo-check -s workspace-write -C . -m gpt-6.1-sol -c model_reasoning_effort=high --json -o last.txt "$PROMPT" < /dev/null > log.jsonl 2> err.txt
else
  env -i HOME=$HOME PATH=$PATH USER=$USER claude -p "$PROMPT" --model $MODEL --effort high --setting-sources "" --strict-mcp-config --permission-mode acceptEdits --allowedTools "Write,Edit,Read" --output-format json > log.json 2> err.txt
fi
RC=$?
END=$(date +%s)
echo "{\"model\":\"$M\",\"task\":\"$T\",\"seconds\":$((END-START)),\"rc\":$RC}" > meta.json
OUT=$BASE/runs/$T/$M; mkdir -p $OUT; cp -f index.html index.svg meta.json $OUT/ 2>/dev/null
cp -f log.json log.jsonl last.txt err.txt $OUT/ 2>/dev/null
echo "done $M $T rc=$RC $((END-START))s $(ls $OUT | tr '\n' ' ')"
