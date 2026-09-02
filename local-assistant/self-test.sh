#!/bin/sh
set -u

fail=0
check() {
  label=$1
  shift
  if "$@" >/dev/null 2>&1; then
    printf 'OK   %s\n' "$label"
  else
    printf 'FAIL %s\n' "$label"
    fail=1
  fi
}

check 'servizio llama.cpp attivo' systemctl --user is-active --quiet local-ai-llama.service
check 'servizio assistente attivo' systemctl --user is-active --quiet local-ai-assistant.service
check 'servizio audio Peppe attivo' systemctl --user is-active --quiet local-ai-audio.service
check 'ascoltatore Peppe attivo' systemctl --user is-active --quiet local-ai-peppe.service
check 'API llama.cpp sana' curl -fsS --max-time 5 http://127.0.0.1:8080/health
check 'API assistente sana' curl -fsS --max-time 5 http://127.0.0.1:8090/health
check 'NVIDIA disponibile' nvidia-smi
if [ "$(prime-select query 2>/dev/null)" = "on-demand" ]; then
  printf 'OK   PRIME on-demand\n'
else
  printf 'FAIL PRIME non è on-demand\n'
  fail=1
fi
if systemctl is-active --quiet ollama.service 2>/dev/null; then
  printf 'FAIL Ollama ridondante ancora attivo\n'
  fail=1
else
  printf 'OK   Ollama ridondante disattivato\n'
fi
check 'Whisper installato' test -x "$HOME/.local/share/local-ai/whisper/whisper-cli"
check 'Piper installato' test -d "$HOME/.local/share/local-ai/piper-runtime/piper"
check 'spotify-player installato' test -x "$HOME/.local/share/local-ai/spotify/spotify_player"
check 'Spotify autenticato' test -f "$HOME/.cache/spotify-player/user_client_token.json"
check 'Tailscale connesso' tailscale status
if [ "$(pactl get-default-source 2>/dev/null)" = "peppe_mic" ] \
   && [ "$(pactl get-default-sink 2>/dev/null)" = "peppe_speaker" ]; then
  printf 'OK   cancellazione eco instradata\n'
else
  printf 'FAIL cancellazione eco non instradata\n'
  fail=1
fi

printf '\nPRIME: '
prime-select query 2>/dev/null || printf 'non disponibile'
printf '\nSalute componenti:\n'
curl -fsS --max-time 5 http://127.0.0.1:8090/health 2>/dev/null || true
printf '\n'

exit "$fail"
