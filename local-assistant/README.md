# Assistente AI locale

Console integrata (assistente e diagnostica): <http://127.0.0.1:8091/>

La precedente pagina dedicata dell'assistente resta disponibile su
<http://127.0.0.1:8090/> e include un pulsante per tornare alla console.

Componenti:

- Qwen3 4B Q4_K_M su llama.cpp/Vulkan e NVIDIA MX250, con contesto da 8192 token;
- risposte mostrate in streaming; modalità **Normale** completa per impostazione
  predefinita, **Rapida** solo su richiesta e **Ragionata** per problemi complessi;
- cache del prefisso attiva e fino a 10 messaggi/16.000 caratteri di cronologia,
  mantenuti entro il contesto del modello;
- Vosk italiano per “Peppe” e “Peppe basta”, Whisper base per i comandi;
- acquisizione always-on dal DSP Intel `DMIC16kHz` nativo;
- Piper `it_IT-paola-medium` per il feedback vocale;
- ricerca DuckDuckGo con lettura protetta delle fonti pubbliche;
- Spotify tramite `spotify-player` e fallback ai controlli KDE;
- accesso remoto previsto tramite Tailscale Serve HTTPS.

## Uso

Non è necessario aprire il monitor: dire **“Ehi Peppe”** o **“Ciao Peppe”**
seguito dalla richiesta.
La conversazione resta aperta per alcuni secondi dopo ogni risposta; dire
**“Peppe basta”** per chiuderla. Il microfono passa attraverso la cancellazione eco WebRTC, così la
musica e la voce di Peppe non dovrebbero riattivarlo.

Nella console integrata si può scrivere oppure usare **Parla** e **Ferma**.
La lettura vocale è disattivata inizialmente per risparmiare risorse e si può
abilitare con **Voce**. La conversazione resta nella stessa pagina insieme a
stato del modello, risorse, trascrizioni e log.

La console diagnostica mostra stato e memoria dei componenti, modello e
versione del motore, contesto, CPU, RAM, swap, disco e VRAM. Le trascrizioni e
i log recenti sono caricati soltanto su richiesta. Le risorse si aggiornano
ogni 10 secondi solo quando la pagina è visibile; la GPU al massimo ogni 15.

Il testo compare mentre viene generato. Peppe usa normalmente la modalità
**Normale**, equivalente al comportamento completo precedente; passa a
**Ragionata** quando la richiesta contiene indicazioni come
“analizza”, “confronta”, “valuta”, “ragiona” o “passo per passo”. Si può forzare
una risposta breve scrivendo “modalità rapida”. Il ragionamento interno non
viene mostrato né letto dalla voce. Il pulsante **Voce** controlla soltanto la
lettura ad alta voce e non riduce la qualità o la lunghezza della risposta.

Esempi:

- “Cerca online le previsioni per domani e cita le fonti.”
- “Quanto spazio e memoria sono disponibili?”
- “Riproduci su Spotify una playlist jazz rilassante.”
- “Metti in pausa Spotify.”
- “Quali dispositivi audio sono disponibili?”
- “Usa il dispositivo Alexa Salotto per Spotify.”

## Sicurezza

Il server ascolta soltanto su localhost. Il modello non dispone di una shell
generica: può usare esclusivamente gli strumenti elencati nell'orchestratore.
Le pagine web possono essere lette soltanto tramite HTTP/HTTPS pubblici; reti
private, loopback e link-local sono bloccati. Nessun testo viene inviato a un
LLM esterno. Tailscale **Serve**, non Funnel, mantiene l'interfaccia privata.

## Servizi

```text
systemctl --user status local-ai-llama.service
systemctl --user status local-ai-assistant.service
systemctl --user status local-ai-audio.service
systemctl --user status local-ai-peppe.service
systemctl --user status local-ai-control.service
```

Prima di installare, adattare percorsi, dispositivi, nomi dei modelli e opzioni
dei servizi all'hardware locale. I file di log specifici della macchina e i
pesi dei modelli non sono inclusi nel repository.

## Licenza

Il codice del progetto è distribuito con licenza Apache-2.0. Modelli, dataset,
pacchetti di sistema e strumenti esterni conservano le rispettive licenze.
