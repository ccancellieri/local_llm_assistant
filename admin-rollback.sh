#!/bin/sh
set -eu

# Ripristina il profilo precedente registrato il 30 agosto 2026.
prime-select nvidia
systemctl enable --now ollama.service
systemctl enable cpupower-gui.service || true
loginctl disable-linger bianco

printf '%s\n' 'Profilo precedente ripristinato. Riavviare il sistema.'
