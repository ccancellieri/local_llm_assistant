#!/usr/bin/env bash
set -u

MODEL="${MODEL:-$HOME/Downloads/Qwen3.8-27B-Uncensored-IQ3_XXS.gguf}"
SERVER="${SERVER:-$HOME/.local/share/local-ai/llama/llama-server}"
PORT=8082
LOG="${LOG:-/tmp/qwen38-peppe-test.log}"
RESULT="${RESULT:-/tmp/qwen38-peppe-test-result.txt}"
REASONING="${REASONING:-off}"
REASONING_BUDGET="${REASONING_BUDGET:-0}"
CASES="${CASES:-strumento-volume}"
MAX_TOKENS="${MAX_TOKENS:-48}"
PID=""

was_active() {
  systemctl --user is-active --quiet "$1"
}

LLAMA_ACTIVE=0
ASSISTANT_ACTIVE=0
PEPPE_ACTIVE=0
was_active local-ai-llama.service && LLAMA_ACTIVE=1
was_active local-ai-assistant.service && ASSISTANT_ACTIVE=1
was_active local-ai-peppe.service && PEPPE_ACTIVE=1

restore() {
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  if [[ "$LLAMA_ACTIVE" == 1 ]]; then
    systemctl --user start local-ai-llama.service || true
    for _ in $(seq 1 90); do
      curl -fsS --max-time 2 http://127.0.0.1:8080/health >/dev/null 2>&1 && break
      sleep 2
    done
  fi
  [[ "$ASSISTANT_ACTIVE" == 1 ]] && systemctl --user start local-ai-assistant.service || true
  [[ "$PEPPE_ACTIVE" == 1 ]] && systemctl --user start local-ai-peppe.service || true
}
trap restore EXIT INT TERM

: > "$RESULT"
if [[ ! -r "$MODEL" ]]; then
  echo "FAIL: model file is not readable" | tee -a "$RESULT"
  exit 2
fi

stat --printf='model_size_bytes=%s\nmodel_mtime=%y\n' "$MODEL" | tee -a "$RESULT"
systemctl --user stop local-ai-peppe.service local-ai-assistant.service local-ai-llama.service
BASE_SWAP_USED_KB=$(awk '/SwapTotal:/ {total=$2} /SwapFree:/ {free=$2} END {print total-free}' /proc/meminfo)

"$SERVER" \
  --model "$MODEL" \
  --alias qwen38-test \
  --host 127.0.0.1 --port "$PORT" \
  --ctx-size 768 --parallel 1 \
  --threads 8 --threads-batch 8 \
  --batch-size 512 --ubatch-size 256 \
  --device Vulkan1 --n-gpu-layers auto \
  --fit on --fit-target 384 --fit-ctx 768 \
  --flash-attn auto --cache-type-k q4_0 --cache-type-v q4_0 \
  --jinja --reasoning "$REASONING" --reasoning-budget "$REASONING_BUDGET" \
  --no-webui >"$LOG" 2>&1 &
PID=$!

READY=0
for _ in $(seq 1 150); do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "FAIL: temporary server exited during loading" | tee -a "$RESULT"
    tail -n 80 "$LOG" >> "$RESULT"
    exit 3
  fi
  MEM_AVAIL_KB=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
  SWAP_TOTAL_KB=$(awk '/SwapTotal:/ {print $2}' /proc/meminfo)
  SWAP_FREE_KB=$(awk '/SwapFree:/ {print $2}' /proc/meminfo)
  SWAP_USED_KB=$((SWAP_TOTAL_KB - SWAP_FREE_KB))
  SWAP_GROWTH_KB=$((SWAP_USED_KB - BASE_SWAP_USED_KB))
  if (( MEM_AVAIL_KB < 450000 || (MEM_AVAIL_KB < 1500000 && SWAP_GROWTH_KB > 400000) )); then
    echo "ABORT_PRESSURE: mem_available_kb=$MEM_AVAIL_KB swap_used_kb=$SWAP_USED_KB swap_growth_kb=$SWAP_GROWTH_KB" | tee -a "$RESULT"
    exit 4
  fi
  if curl -fsS --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done

if [[ "$READY" != 1 ]]; then
  echo "FAIL: model did not become ready within 300 seconds" | tee -a "$RESULT"
  tail -n 80 "$LOG" >> "$RESULT"
  exit 5
fi

echo "READY" | tee -a "$RESULT"
free -h >> "$RESULT"
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader >> "$RESULT" 2>&1 || true
python3 local-assistant/llm-eval.py \
  --url "http://127.0.0.1:${PORT}/v1/chat/completions" \
  --model qwen38-test --max-tokens "$MAX_TOKENS" --timeout 300 \
  --cases "$CASES" >> "$RESULT" 2>&1
EVAL_STATUS=$?
echo "eval_status=$EVAL_STATUS" | tee -a "$RESULT"
tail -n 120 "$LOG" >> "$RESULT"
exit "$EVAL_STATUS"
