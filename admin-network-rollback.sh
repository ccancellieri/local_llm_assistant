#!/bin/sh
set -eu

# Disattiva accesso e proxy senza rimuovere pacchetti o configurazioni.
tailscale serve reset || true
tailscale down || true
systemctl disable --now tailscaled

printf '%s\n' 'Tailscale e relativo proxy sono stati disattivati.'
