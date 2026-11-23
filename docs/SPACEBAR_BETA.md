# Beta Spacebar — guida operativa (Windows / PowerShell)

Stack locale e isolato che esegue il **codice reale** del bot contro un server
Spacebar self-hosted. Serve a validare il trasporto (REST, Gateway, slash
command) senza toccare Discord, OpenAI o i dati di produzione.

## Cosa fa e cosa non fa

| Fa | Non fa |
|---|---|
| Avvia Spacebar (gateway, API, CDN, PostgreSQL 18, RabbitMQ) su `127.0.0.1` | Non pubblica nulla sulla LAN |
| Avvia il bot con `SAKURA_BOT_PLATFORM=spacebar` sullo **stesso codice** di produzione | Non avvia lo stack di produzione |
| Usa PostgreSQL e Redis beta dedicati, con volumi propri | Non monta `.env`, volumi o reti di produzione |
| Punta l'SDK OpenAI a un mock locale deterministico | Non effettua chiamate pagate a OpenAI |
| Blocca l'egress del bot verso `discord.com`, `gateway.discord.gg`, `api.openai.com` | Non sostituisce il test su Discord reale (staging) |

Il bot beta **non pubblica porte**: vive solo su una rete Docker `internal: true`.
Le probe `/health` e `/ready` si leggono dall'interno dello stack (vedi sotto).

## Prerequisiti

- Windows 10/11 con Docker Desktop e backend WSL2 attivo.
- Git for Windows per clonare il repository; nessun altro runtime locale.
- Circa **10 GB** liberi: le tre immagini Spacebar pesano ~2,9 GB ciascuna, più
  PostgreSQL 18 e RabbitMQ.
- Porte libere su `127.0.0.1`: **3001**, **3002**, **3003**. Se sono occupate,
  cambiarle in `.env.spacebar` (`SPACEBAR_GATEWAY_PORT`, `SPACEBAR_API_PORT`,
  `SPACEBAR_CDN_PORT`).

## File coinvolti

| File | Ruolo | Versionato |
|---|---|---|
| `docker-compose.spacebar.yml` | Stack beta completo, progetto `sakura-spacebar-beta` | sì |
| `docker-compose.spacebar.evidence.yml` | Relay `socat` che pubblica `/health` e `/ready` su `127.0.0.1:3004`, solo per gli screenshot del README | sì |
| `.env.spacebar.example` | Modello delle variabili con placeholder | sì |
| `.env.spacebar` | Valori locali reali (password, token del bot) | **no** (gitignored) |
| `spacebar-beta/ai-mock/` | Stub OpenAI-compatibile, solo standard library | sì |
| `spacebar-beta/init_config.py` | Completa il `config.json` generato da Spacebar | sì |
| `spacebar-beta/spike/` | Script di verifica (spike, probe, egress, AI) | sì |
| `spacebar-beta/data/` | `config.json`, chiavi JWT e CDN generati a runtime | **no** (gitignored) |
| `sakura-bot/core/platform.py` | Adapter del trasporto, attivo solo in modalità `spacebar` | sì |

Le immagini Spacebar sono fissate **per digest** (il progetto pubblica solo il tag
mobile `latest`), quindi un `pull` successivo non cambia lo stack senza una
modifica esplicita del file.

## Primo avvio

Eseguire dalla cartella radice del repository.

```powershell
# 1. Creare la configurazione locale a partire dal modello.
Copy-Item .env.spacebar.example .env.spacebar

# 2. Scegliere password locali proprie, diverse da quelle di produzione.
notepad .env.spacebar

# 3. Validare il file Compose senza avviare nulla.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml config --quiet

# 4. Avviare i componenti Spacebar: al primo avvio generano config.json e le chiavi.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml up -d spacebar-db rabbitmq spacebar-gateway spacebar-api spacebar-cdn

# 5. Attendere la generazione dei file, poi fermare i tre servizi Spacebar.
Start-Sleep -Seconds 45
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml stop spacebar-gateway spacebar-api spacebar-cdn
```

A questo punto esiste `spacebar-beta/data/config.json`, generato con endpoint
`null` che Spacebar rifiuta. Va completato una sola volta con i valori interni
(il bot parla con i container, il browser con `127.0.0.1`):

```powershell
.\.venv\Scripts\python.exe spacebar-beta\init_config.py
```

Lo script imposta `api`, `gateway`, `cdn`, `rabbitmq` e disattiva il captcha di
registrazione (nessun servizio captcha è configurato in locale). Le porte host si
cambiano con `--api-port`, `--gateway-port`, `--cdn-port`.

Riavviare i servizi Spacebar perché leggano la nuova configurazione:

```powershell
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml up -d
Start-Sleep -Seconds 40
Invoke-WebRequest -Uri 'http://127.0.0.1:3002/api/v9/gateway' -UseBasicParsing
```

La risposta attesa è `{"url":"ws://127.0.0.1:3001/"}`.

## Bootstrap del server locale (una sola volta)

Servono un utente proprietario, un'applicazione bot e una guild. I comandi
seguenti sono quelli effettivamente usati e verificati in questa sessione.

```powershell
# 1. Registrare l'utente proprietario. `consent` e `date_of_birth` sono
#    obbligatori; la password richiede >= 8 caratteri, 2 maiuscole, 2 numeri.
$body = @{ username='sakuraowner'; password='SakuraBeta11'; date_of_birth='2000-01-01'; consent=$true } | ConvertTo-Json
$reg = Invoke-RestMethod -Uri 'http://127.0.0.1:3002/api/v9/auth/register' -Method Post -Body $body -ContentType 'application/json'
$userToken = $reg.token

# 2. Creare l'applicazione e poi il bot user: sono due chiamate distinte.
$app = Invoke-RestMethod -Uri 'http://127.0.0.1:3002/api/v9/applications' -Method Post -Headers @{ Authorization = $userToken } -Body (@{ name='Sakura Beta Bot' } | ConvertTo-Json) -ContentType 'application/json'
$bot = Invoke-RestMethod -Uri "http://127.0.0.1:3002/api/v9/applications/$($app.id)/bot" -Method Post -Headers @{ Authorization = $userToken } -ContentType 'application/json'

# 3. Scrivere le credenziali nel file locale (mai in chat, mai in Git).
$envFile = Get-Content .env.spacebar -Raw
$envFile = $envFile -replace 'SPACEBAR_BOT_TOKEN=.*', "SPACEBAR_BOT_TOKEN=$($bot.token)"
$envFile = $envFile -replace 'SPACEBAR_BOT_CLIENT_ID=.*', "SPACEBAR_BOT_CLIENT_ID=$($app.id)"
Set-Content -Path .env.spacebar -Value $envFile -NoNewline -Encoding utf8

# 4. Il bot crea la propria guild: Spacebar vieta ai bot l'endpoint inviti.
Invoke-RestMethod -Uri 'http://127.0.0.1:3002/api/v9/guilds' -Method Post -Headers @{ Authorization = "Bot $($bot.token)" } -Body (@{ name='Sakura Beta Guild' } | ConvertTo-Json) -ContentType 'application/json'

# 5. Avviare il bot con le credenziali appena scritte.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml up -d sakura-bot-beta
```

Verifica dell'identità del bot (deve rispondere `bot: true`):

```powershell
$token = ((Get-Content .env.spacebar | Select-String 'SPACEBAR_BOT_TOKEN=') -split '=',2)[1].Trim()
Invoke-RestMethod -Uri 'http://127.0.0.1:3002/api/v9/users/@me' -Headers @{ Authorization = "Bot $token" }
```

> **Nota verificata:** `POST /api/v9/auth/login` con utente e password ha
> risposto `Invalid login or password` anche subito dopo una registrazione
> riuscita. Usare il token restituito dalla registrazione, come sopra.

## Verifica dello stack

```powershell
# Stato dei servizi.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml ps

# /health e /ready dall'interno: il bot non pubblica porte.
Get-Content spacebar-beta\spike\probe.py -Raw | docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml exec -T sakura-bot-beta python -

# Isolamento: i servizi esterni devono risultare BLOCKED, il mock raggiungibile.
Get-Content spacebar-beta\spike\egress_check.py -Raw | docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml exec -T sakura-bot-beta python -

# Integrazione AI con il mock deterministico.
Get-Content spacebar-beta\spike\ai_mock_check.py -Raw | docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml exec -T sakura-bot-beta python -
```

Output atteso di `/ready`:

```json
{"checks": {"bootstrap": true, "cache": true, "database": true, "discord": true, "extensions": true}, "status": "ready"}
```

## Comandi quotidiani

```powershell
# Log del bot.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml logs -f sakura-bot-beta

# Log dei servizi Spacebar.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml logs -f spacebar-api spacebar-gateway

# Fermare tutto mantenendo i dati.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml down

# Riavviare solo il bot dopo una modifica al codice.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml up -d --build sakura-bot-beta
```

## Reset del solo ambiente beta

Il comando seguente elimina **solo** i volumi del progetto `sakura-spacebar-beta`
(database Spacebar, RabbitMQ, database Sakura beta). Non tocca `sakura-spirit-bot`
né gli stack di test.

```powershell
# Verificare il nome del progetto prima di procedere.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml config --format json | Select-String '"name"'

# Reset: container e volumi del solo progetto beta.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml down -v
Remove-Item -Recurse -Force spacebar-beta\data
```

Dopo il reset bisogna ripetere "Primo avvio" e "Bootstrap del server locale":
`config.json`, le chiavi JWT, l'utente, il bot e la guild vengono ricreati.

## Problemi frequenti

| Sintomo | Causa | Rimedio |
|---|---|---|
| `required variable SPACEBAR_BOT_TOKEN is missing a value` | `.env.spacebar` non compilato | Completare il bootstrap e riscrivere le due variabili |
| Spacebar non parte, log `Your config has invalid values` | `config.json` con endpoint `null` | Eseguire `spacebar-beta\init_config.py` e riavviare |
| `port is already allocated` | Porta 3001/3002/3003 occupata | Cambiare `SPACEBAR_*_PORT` in `.env.spacebar` |
| Bot in `Restarting` con `LoginFailure` | Token Spacebar non valido o bot non creato | Rifare i passi 2-3 del bootstrap |
| `Invalid platform configuration: ... public service host` | Endpoint puntato a `discord.com` | Correggere `SAKURA_BOT_API_BASE_URL`; è il comportamento voluto |
| `CommandSyncFailure ... must be array` | Adapter `contexts`/`integration_types` non applicato | Verificare che `SAKURA_BOT_PLATFORM=spacebar` |
| `/ready` risponde 503 con `discord: false` | Gateway Spacebar non raggiungibile | Controllare `spacebar-gateway` e `SAKURA_BOT_GATEWAY_URL` |
| Dati persi dopo `down` | È stato usato `down -v` | Comportamento atteso: `-v` elimina i volumi |

## Limiti noti di questa guida

- Il client web (Fermi) **non** è incluso nello stack: la documentazione
  ufficiale non fornisce un'immagine Docker e richiede una build da sorgente.
  Senza client non è possibile verificare la resa grafica né l'invio reale di
  un'interazione; vedi `docs/SPACEBAR_COMPATIBILITY.md`.
- Spacebar non implementa thread, voice/video completo, auto moderation e
  OAuth2 con scope: le funzionalità del bot che ne dipendono restano da
  verificare su Discord staging.
