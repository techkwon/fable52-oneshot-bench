#!/bin/zsh
# usage: run_one.sh <model: fable|opus|gpt|carbon> <task> <workdir>
M=$1; T=$2
BASE=.
WORK="$3/$T/$M"; mkdir -p "$WORK"; cd "$WORK"
PROMPT="$(cat $BASE/prompts/$T.txt)"
START=$(date +%s)
case $M in
  fable) MODEL=claude-fable-5-2;;
  opus)  MODEL=claude-opus-5-5;;
esac
if [[ $M == carbon ]]; then
  # Gemini 4 Carbon via Antigravity CLI (agy), Gemini API key from Keychain. Custom model has no effort levels.
  # First try used --mode accept-edits: in headless mode agy ends the whole turn when a shell command is denied,
  # so 4 of 5 tasks produced nothing (svg had already written its file). Re-run with sandboxed commands allowed,
  # which matches the codex workspace-write sandbox GPT ran in.
  env -i HOME=$HOME PATH=$PATH USER=$USER GEMINI_API_KEY="$(security find-generic-password -a "$USER" -s agy-gemini-api-key -w)" agy -p "$PROMPT" --model gemini-4-carbon --sandbox --dangerously-skip-permissions --output-format json < /dev/null > log.json 2> err.txt
elif [[ $M == gpt ]]; then
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
