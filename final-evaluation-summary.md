# Esito MiniCPM sul laptop di Peppe — 7 ottobre 2026

**Provato sul laptop: eseguibile e rapido, ma non consigliato come sostituto per Peppe in italiano.**

Confronto reale di45 richieste per modello, temperatura 0,2, 96 token massimi, contesto 2048 e Whisper residente:

| Misura | Qwen3-4B Q4_K_M | MiniCPM5-2B Q4_K_M |
|---|---:|---:|
| Primo testo, mediana | 0,619 s | 0,364 s |
| Risposta completa, mediana | 1,504 s | 0,880 s |
| Generazione | 14,51 token/s | 24,78 token/s |
| Picco VRAM totale | 3487 MiB | 2335 MiB |
| Comandi JSON conformi | 10/20 | 10/20 |

MiniCPM produce spiegazioni italiane scorrette e XML al posto del JSON atteso per ora e dispositivi. Altre45 richieste con il campionamento ufficiale ottengono9/20 comandi conformi e non risolvono la qualità italiana. Due controlli con ragionamento attivo non risolvono gli errori.

Whisper mantiene le stesse trascrizioni su15 confronti. Mediane ASR: 1,513 s prima, 1,686 s con MiniCPM residente, 1,822 s dopo lo scaricamento: nessuna attribuzione causale del rallentamento è possibile con questo test sequenziale.

Il backend corrente `peppe-fast` risponde403 per incompatibilità fra connessione Groq e permessi della chiave; non è stato modificato.

MiniCPM temporaneo spento, GPU tornata a929 MiB, servizi originali attivi. Nessun test con microfono, playback o strumenti eseguiti. Il precedente consiglio MiniCPM-o 4.5 era basato su dati errati: quel modello ha 9B parametri e non è stato provato.

Vedi `evaluation-minicpm.md` per configurazione, limiti ed evidenze.
