#!/bin/sh
set -eu

systemctl --user disable --now local-ai-peppe.service local-ai-audio.service
config="$HOME/.config/pipewire/pipewire-pulse.conf.d/peppe-echo-cancel.conf"
if [ -f "$config" ]; then
    mv "$config" "$config.disabled"
fi
systemctl --user restart pipewire-pulse.service
sleep 3
pactl set-default-source alsa_input.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__Mic1__source
pactl set-default-sink alsa_output.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__Speaker__sink
pactl set-source-volume alsa_input.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__Mic1__source 47%
echo "Peppe disattivato; configurazione conservata come peppe-echo-cancel.conf.disabled"
