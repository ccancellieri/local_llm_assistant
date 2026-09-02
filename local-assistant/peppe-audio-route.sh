#!/bin/sh
set -eu

attempt=0
while [ "$attempt" -lt 30 ]; do
    if pactl list short sources | grep -q '[[:space:]]peppe_mic[[:space:]]' \
       && pactl list short sinks | grep -q '[[:space:]]peppe_speaker[[:space:]]'; then
        pactl set-source-volume alsa_input.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__Mic1__source 75%
        pactl set-sink-volume alsa_output.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__Speaker__sink 90%
        pactl set-sink-volume peppe_speaker 100%
        pactl set-default-source peppe_mic
        pactl set-default-sink peppe_speaker
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep 1
done

echo "Dispositivi di cancellazione eco non disponibili" >&2
exit 1
