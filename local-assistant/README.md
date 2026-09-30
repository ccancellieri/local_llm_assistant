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
- Spotify Connect tramite le API ufficiali, con la riproduzione nell'app grafica Spotify;
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
- “Hey Peppe, suona Ryden su Echo Plus.”

## Spotify Connect

Serve Spotify Premium e un'app personale nel [Developer Dashboard di Spotify](https://developer.spotify.com/dashboard).
Nell'app, registrare esattamente il redirect URI `http://127.0.0.1:8181/callback`.
Salvare il Client ID pubblico in `~/.config/local-ai/spotify-client-id` (una riga,
solo l'identificativo), poi sul computer che esegue Peppe avviare:

```text
python3 ~/.local/share/local-ai/assistant/spotify_connect.py --login
```

Il browser chiede una sola autorizzazione. Peppe salva il token in
`~/.config/local-ai/spotify-connect-token.json` con permessi 600 e lo rinnova
automaticamente. Aprire l'app Spotify grafica e rendere visibile Echo Plus in
Spotify Connect prima di chiedere la riproduzione. Se Echo Plus non compare o
esistono dispositivi con lo stesso nome, Peppe non avvia il brano su un'altra
uscita. Il Client ID può anche essere fornito con `SPOTIFY_CLIENT_ID` nel
servizio, mantenendolo disponibile per il rinnovo del token.

## Sicurezza

Il server ascolta soltanto su localhost. Il modello non dispone di una shell
generica: può usare esclusivamente gli strumenti elencati nell'orchestratore.
Le pagine web possono essere lette soltanto tramite HTTP/HTTPS pubblici; reti
private, loopback e link-local sono bloccati. Con il backend locale predefinito
nessun testo viene inviato a un LLM esterno; con un provider remoto tramite
OmniRoute si applicano le condizioni descritte sotto. Tailscale **Serve**, non
Funnel, mantiene l'interfaccia privata ai dispositivi connessi alla stessa tailnet.

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

## Backend tramite OmniRoute

Peppe può usare OmniRoute conservando gli strumenti, la voce e lo streaming della
console. Il gateway può instradare verso un provider remoto oppure verso un
modello locale indipendente, tramite un provider compatibile OpenAI.

Configurare nel servizio dell'assistente:

```ini
[Service]
Environment=LLAMA_URL=http://127.0.0.1:20128/v1/chat/completions
Environment=LOCAL_LLM_MODEL=provider/model
Environment=LOCAL_LLM_HEALTH_URL=http://127.0.0.1:20128/healthz
Environment=LOCAL_LLM_API_KEY_FILE=%h/.config/local-ai/omniroute.key
```

Per risposte rapide per impostazione predefinita, aggiungere
`LOCAL_ASSISTANT_DEFAULT_PROFILE=fast` al servizio dell'assistente. Le risposte
ordinarie hanno un limite di 160 token (96 in voce), senza richiedere ragionamento
aggiuntivo. Le richieste esplicite di analisi conservano il profilo ragionato.
La latenza dipende anche dalla coda del provider: questo limite non garantisce un
tempo massimo di risposta.

Quando il gateway sostituisce il modello locale, configurare anche il servizio
della console con `LOCAL_LLM_SERVICE=omniroute.service` e lo stesso
`LOCAL_LLM_MODEL`. I controlli e i log della console useranno il servizio gateway,
senza tentare di avviare llama.cpp. Le metriche specifiche di llama.cpp rimarranno
sconosciute. Disabilitare separatamente l'avvio automatico del modello locale;
conservare la configurazione per un eventuale ripristino.

Sostituire `provider/model` con l'identificativo esatto configurato nel gateway.
Il file della chiave deve essere leggibile solo dall'utente del servizio
(`chmod 600`); non inserire la chiave nella pagina web o nel repository.
Un file mancante o vuoto interrompe la richiesta prima della chiamata HTTP.
Senza queste impostazioni resta attivo il collegamento diretto a llama.cpp.

Per un percorso esclusivamente locale, limitare la chiave nel gateway al modello
e alla connessione locali, disabilitando fallback esterni e selezione automatica.
Un provider remoto può inviare a terzi testo, cronologia e risultati degli strumenti:
abilitarlo solo come scelta esplicita. Il controllo `/health` verifica il servizio
configurato; la disponibilità effettiva del modello richiede anche una prova di
generazione. Usare HTTPS se il gateway si trova su un altro dispositivo. Non
esporre la console amministrativa direttamente su Internet.
