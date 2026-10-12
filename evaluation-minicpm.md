# MiniCPM sul laptop di Peppe — prove del 7 ottobre 2026

## Esito

**MiniCPM5-2B Q4_K_M è eseguibile sul laptop e più rapido di Qwen3-4B, ma non è qualificato come sostituto di Peppe in italiano.** I problemi di qualità linguistica e di formato dei comandi rimangono sia con i parametri del profilo rapido sia con il campionamento raccomandato dal produttore. Nessuna sostituzione del backend è stata effettuata.

Questo documento sostituisce la precedente valutazione teorica: le percentuali di accuratezza italiana e le proiezioni VRAM precedenti non erano misurate. MiniCPM-o 4.5 è un modello da 9B parametri, non 4,5B; non è stato scaricato né provato.

## Configurazione verificata

- Laptop Linux x86_64, NVIDIA GeForce MX250 con 4096 MiB VRAM, 15650 MiB RAM.
- Whisper Turbo Q5 residente: 929 MiB VRAM prima e dopo le prove.
- Runtime già installato: llama.cpp build 10672, commit 511f9c137, backend **Vulkan1** sulla MX250. Nessun aggiornamento del runtime.
- Modello MiniCPM: `MiniCPM5-2B-Q4_K_M.gguf`, 1561318368 byte.
- Revisione Hugging Face: `2079a22f3beaa4e306449978533478fe0522f4b3`.
- SHA256 verificato contro i metadati ufficiali: `ec2d5801640099e97d8d7e8003ad4d81f336e757811f03a26173dddf386602fd`.
- Server temporanei, uno alla volta: loopback porta 18084; contesto 2048; un solo slot; 4 thread; batch 256/ubatch 128; tutti gli strati GPU; cache K/V q8_0; Jinja; ragionamento disattivato per il profilo rapido.

Fonti: [MiniCPM5-2B GGUF ufficiale](https://huggingface.co/openbmb/MiniCPM5-2B-GGUF), [MiniCPM-o 4.5 ufficiale](https://huggingface.co/openbmb/MiniCPM-o-4_5).

## Metodo e misure principali

Nove richieste sintetiche, ripetute cinque volte: volume, ora, pausa musica, dispositivi audio, calcolo dello sconto, cielo azzurro, totani, rifiuto di inventare un'azione eseguita, memoria del nome Marco. Prompt di sistema estratto dal sorgente effettivamente installato di Peppe. Streaming HTTP diretto, limite96 token, strumenti mai eseguiti.

Il confronto principale usa temperatura 0,2, come Peppe; top_p 0,95 e min_p 0. Ogni modello ha completato45 richieste senza errori HTTP né troncamenti. I tempi sono mediane di questa piccola campagna, con cache del prefisso, non garanzie di latenza per conversazioni reali. I testi e le lunghezze delle risposte differiscono: il tempo totale non misura da solo la velocità a parità di contenuto.

| Misura | Qwen3-4B Q4_K_M | MiniCPM5-2B Q4_K_M |
|---|---:|---:|
| Primo testo, mediana | 0,619 s | 0,364 s |
| Risposta completa, mediana | 1,504 s | 0,880 s |
| Generazione, mediana | 14,51 token/s | 24,78 token/s |
| Picco VRAM totale con Whisper | 3487 MiB | 2335 MiB |
| Picco RSS server LLM | 2939964 KiB | 1924468 KiB |
| JSON comandi esattamente conforme | 10/20 | 10/20 |

L'inizializzazione del server registrata nei log è 5,56s per Qwen e 2,84s per MiniCPM; non equivale al tempo di risposta alla prima domanda. I picchi di memoria sono campionati e possono perdere eventi molto brevi.

## Qualità e compatibilità

MiniCPM a temperatura 0,2:
- Volume e pausa musica: JSON atteso in tutte le ripetizioni.
- Ora e dispositivi: output XML `<function ...>` al posto del contratto JSON di Peppe, in tutte le ripetizioni.
- Calcolo e nome Marco: risposte corrette nei casi osservati.
- Cielo azzurro: spiegazioni errate.
- Totani: risposte che parlano di corteccia, foglie o riparazioni.

Anche Qwen fallisce due categorie di comando e produce errori qualitativi: non è un riferimento di qualità certificato. I conteggi riportati sono conformità su queste quattro categorie, non accuratezza generale.

Ulteriore campagna a temperatura 1,0, top_p 0,95, min_p 0, come raccomandato da OpenBMB: altre45 richieste per modello. MiniCPM ottiene9/20 comandi conformi, mediana completa0,926s, un troncamento; gli errori italiani persistono. Qwen ottiene11/20, un troncamento.

Quattro controlli mirati con prompt più semplice: MiniCPM identifica correttamente gli squid in inglese; in italiano, anche con ragionamento attivo e un limite512 token, risponde «I totani sono un'informazione» e dà una spiegazione scorretta del cielo. Un output contiene inoltre il marcatore `</think>`. Questo prova un limite nelle configurazioni esaminate, non che ogni possibile configurazione MiniCPM sia inutilizzabile.

## Convivenza con Whisper

Tre clip pubbliche FLEURS italiane già presenti sul laptop, cinque ripetizioni ciascuna; nessun microfono o playback.

| Condizione | Richieste | Mediana ASR |
|---|---:|---:|
| Prima di caricare LLM | 15 | 1,513 s |
| MiniCPM residente, campionatore risorse spento | 15 | 1,686 s |
| Dopo aver scaricato MiniCPM dalla GPU | 15 | 1,822 s |

Trascrizioni identiche in tutte le15 coppie confrontate. Il rallentamento resta anche dopo lo scaricamento del modello: queste prove sequenziali non permettono di attribuirlo causalmente a MiniCPM. Temperatura, clock e carichi di sistema non sono stati controllati.

Un gruppo preliminare con campionatore attivo aveva mediana1,794s. La sua ultima richiesta può essersi sovrapposta all'inizio della successiva campagna LLM; per un confronto senza sovrapposizione si usano soltanto le prime 14 coppie, conservate nei dati grezzi. La campagna di conferma riportata sopra non ha quella sovrapposizione.

## Backend attuale e stato finale

Il confronto con `peppe-fast` non ha prodotto risposte:45 richieste hanno restituito403. Un controllo minimo ha mostrato che la combo tenta Groq ma la chiave di Peppe esclude quella connessione. Nessuna modifica a chiavi, combo o permessi.

A fine prova i server LLM temporanei sono fermati; GPU 929 MiB; assistente, listener e Whisper sono attivi come all'inizio; il servizio LLM di produzione resta mascherato. Il GGUF scaricato resta nella cartella isolata `minicpm-trial` del laptop per eventuali ulteriori confronti.

## Decisione

Non adottare questa configurazione MiniCPM come backend italiano di Peppe. Il risparmio di memoria e la velocità sono verificati, ma non compensano risposte scorrette e comandi incompatibili. Non sono stati provati input dal microfono, tempi fino alla voce, eco, interruzioni durante il parlato o conversazioni lunghe. I dati grezzi e gli script della campagna sono conservati insieme al rapporto nella cartella di risultati `peppe-minicpm-trial`.
