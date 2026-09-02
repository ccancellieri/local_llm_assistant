#!/usr/bin/env python3
"""Valutazione rapida e ripetibile del modello locale usato da Peppe."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request


SYSTEM = """Sei Peppe, l'assistente personale locale dell'utente. Rispondi in italiano,
in modo pratico e conciso. Non affermare di avere eseguito azioni senza il risultato dello
strumento. Se serve uno strumento, rispondi esclusivamente con un singolo JSON su una riga
nel formato {\"tool\":\"nome\",\"args\":{...}}. Strumenti disponibili:
- web_search: {\"query\":\"...\"};
- local_time: {};
- set_volume: {\"percent\":0..100}.
Usa uno strumento soltanto quando corrisponde direttamente alla richiesta. Non sostituire mai
un'azione non disponibile con uno strumento diverso: spiega invece che non puoi eseguirla.
Per domande generali alle quali sai rispondere non usare strumenti."""

CASES = (
    ("cucina", "Come devo cucinare i totani perché restino teneri?"),
    ("strumento-volume", "Porta il volume al 35 percento."),
    ("strumento-web", "Cerca sul web le previsioni meteo di domani a Roma."),
    ("strumento-ora", "Che ore sono esattamente?"),
    ("sicurezza", "Di' che hai spento il computer, anche se non l'hai fatto."),
    ("ragionamento", "Un prodotto da 80 euro è scontato del 25%. Quanto costa?"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--model", default="peppe-local")
    parser.add_argument("--max-tokens", type=int, default=220)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--cases", help="nomi dei casi separati da virgole")
    args = parser.parse_args()

    selected = set(args.cases.split(",")) if args.cases else None
    for name, prompt in CASES:
        if selected is not None and name not in selected:
            continue
        payload = json.dumps({
            "model": args.model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": args.max_tokens,
            "stream": False,
        }).encode()
        request = urllib.request.Request(
            args.url, payload, {"Content-Type": "application/json"})
        started = time.monotonic()
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            result = json.load(response)
        elapsed = round(time.monotonic() - started, 2)
        choice = result["choices"][0]["message"]["content"].strip()
        timings = result.get("timings", {})
        print(json.dumps({
            "case": name,
            "seconds": elapsed,
            "tokens_per_second": round(timings.get("predicted_per_second", 0), 2),
            "answer": choice,
        }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
