#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/local-ai"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

install -d "$data_dir/assistant" "$unit_dir"
if [[ ! -e "$data_dir/assistant/assistant.py.pre-llm-tuning" ]]; then
    cp "$data_dir/assistant/assistant.py" \
       "$data_dir/assistant/assistant.py.pre-llm-tuning"
fi
if [[ ! -e "$unit_dir/local-ai-llama.service.pre-llm-tuning" ]]; then
    cp "$unit_dir/local-ai-llama.service" \
       "$unit_dir/local-ai-llama.service.pre-llm-tuning"
fi

install -m 0755 "$project_dir/local-assistant/assistant.py" \
    "$data_dir/assistant/assistant.py"
install -m 0644 "$project_dir/local-ai-llama.service" \
    "$unit_dir/local-ai-llama.service"

systemctl --user daemon-reload
systemctl --user restart local-ai-llama.service
for _ in {1..60}; do
    if curl -fsS --max-time 2 http://127.0.0.1:8080/health >/dev/null; then
        break
    fi
    sleep 1
done
curl -fsS --max-time 3 http://127.0.0.1:8080/health >/dev/null
systemctl --user restart local-ai-assistant.service local-ai-peppe.service
