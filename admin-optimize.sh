#!/bin/sh
set -eu

# Modifica minima e reversibile per il profilo AI locale.
prime-select on-demand
systemctl disable --now ollama.service
systemctl disable --now cpupower-gui.service || true
loginctl enable-linger bianco
printf '%s\n' 'Ottimizzazione amministrativa completata. Riavviare il sistema.'
