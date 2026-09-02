#!/bin/sh
set -eu

# Repository ufficiale Tailscale per Ubuntu 26.04 (resolute).
install -d -m 0755 /usr/share/keyrings
curl -fsSL -o /usr/share/keyrings/tailscale-archive-keyring.gpg \
  https://pkgs.tailscale.com/stable/ubuntu/resolute.noarmor.gpg
curl -fsSL -o /etc/apt/sources.list.d/tailscale.list \
  https://pkgs.tailscale.com/stable/ubuntu/resolute.tailscale-keyring.list
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y tailscale
systemctl enable --now tailscaled

printf '%s\n' 'Tailscale installato. Eseguire ora: sudo tailscale up'
