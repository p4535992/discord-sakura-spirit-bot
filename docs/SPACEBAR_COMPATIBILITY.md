# Compatibilità Spacebar — matrice verificata

Stato delle verifiche eseguite il **23 novembre 2026** contro lo stack
`docker-compose.spacebar.yml` (progetto `sakura-spacebar-beta`) con
`discord.py==2.7.1`, Python 3.13, PostgreSQL 18 (Spacebar) e 16.15 (Sakura),
RabbitMQ 4.

Legenda degli stati:

- **PASS** — verificato con evidenza diretta in questa sessione.
- **FAIL** — verificato e non funzionante.
- **NOT_SUPPORTED_SPACEBAR** — il server dichiara o dimostra di non supportarlo.
- **NOT_RUN** — non eseguibile in questa sessione (manca il client web).

## Versioni e immagini

| Componente | Riferimento usato |
|---|---|
| `spacebar-gateway` | `ghcr.io/spacebarchat/server-gateway@sha256:7d64708e…` |
| `spacebar-api` | `ghcr.io/spacebarchat/server-api@sha256:232dcf4c…` |
| `spacebar-cdn` | `ghcr.io/spacebarchat/server-cdn@sha256:d686e573…` |
| Database Spacebar | `postgres:18-alpine` |
| Broker | `rabbitmq:4-management-alpine` |
| API attive dichiarate dal server | versioni `6`, `7`, `8`, `9` (default `9`) |

Le immagini Spacebar sono pubblicate solo con il tag mobile `latest`: nello stack
sono fissate per digest, quindi restano riproducibili.

## Trasporto e protocollo

| # | Verifica | Stato | Evidenza |
|---|---|---|---|
| 1 | Redirect REST (`discord.http.Route.BASE` → `/api/v9`) | PASS | `GET /users/@me` con `Authorization: Bot …` risponde `bot: true` |
| 2 | Redirect Gateway (`DiscordWebSocket.DEFAULT_GATEWAY` → `ws://spacebar-gateway:3001/`) | PASS | READY ricevuto, `Logged in as Sakura Beta Bot 2#8133` |
| 3 | Heartbeat e sessione Gateway | PASS | connessione stabile per tutta la sessione, nessuna riconnessione |
| 4 | `on_ready` e presenza | PASS | log `Sakura Spirit Bot is ready!` |
| 5 | Guild e canali visibili al bot | PASS | `Connected to 1 guilds`, `1 text, 0 voice` |
| 6 | Invio messaggio in canale | PASS | `id=1574504994181222498 in #general` |
| 7 | Sync slash command globali (`tree.sync()`) | PASS | `Synced 25 slash commands` |
| 8 | Lettura comandi registrati (`tree.fetch_commands`) | PASS | 25 comandi con descrizioni via `GET /applications/{id}/commands` |
| 9 | Persistenza dopo riavvio del bot | PASS | `/ready` 200 e 25 comandi ri-sincronizzati dopo `restart` |
| 10 | `/health` e `/ready` | PASS | `/ready` 200 con `bootstrap`, `cache`, `database`, `discord`, `extensions` tutti `true` |
| 11 | Blocco egress del bot | PASS | `discord.com`, `gateway.discord.gg`, `api.openai.com` → `gaierror` |
| 12 | Fail-fast su endpoint pubblico | PASS | exit 1: `Invalid platform configuration: … points at a public service host ('discord.com')` |
| 13 | AI locale deterministica | PASS | testo, JSON personalità e JSON emozione dal mock |
| 14 | Invocazione di uno slash command (`POST /interactions`) | PASS | `POST /api/v9/interactions` → 204, il bot riceve l'evento ed esegue il comando |
| 15 | Risposta con embed nella risposta iniziale | PASS | `sakura-help` → embed `🌸 Sakura Spirit Bot - Help` in `#general` |
| 16 | Secondo comando sullo stesso canale | PASS | `sakura-server-info` → embed `🌸 Sakura Beta Guild` |
| 17 | Stato scritto da un comando e riletto da un altro | PASS | `sakura-spirit-adopt` → `sakura-my-spirit` mostra `🌸 Hanami` |
| 18 | AI locale invocata da un comando | PASS | `POST /v1/chat/completions` 200 sul mock durante `sakura-spirit-interact` |
| 19 | Comando che chiama `defer()` prima di una risposta lenta | PASS (con adattamento I) | `sakura-spirit-adopt` e `sakura-spirit-interact` rispondono con embed |
| 20 | Log del bot pulito durante le invocazioni | PASS | nessun `ERROR`/`Traceback` nei log dopo la sequenza di cinque invocazioni |

## Incompatibilità reali trovate (e adattate)

| # | Problema | Effetto senza adattamento | Adattamento |
|---|---|---|---|
| A | Spacebar risponde `application/json; charset=utf-8`, discord.py confronta `content-type == 'application/json'` per uguaglianza esatta | ogni risposta torna come stringa: `TypeError: string indices must be integers` durante il login | `core/platform.py` sostituisce `discord.http.json_or_text` |
| B | discord.py invia `contexts`/`integration_types` a `null`; lo schema Spacebar richiede array | `CommandSyncFailure` HTTP 400, codice 50035, `must be array` | `core/platform.py` fa restituire `[]` a `_merge_to_array` |
| C | `GET /gateway/bot` restituisce l'endpoint **pubblico** (`ws://127.0.0.1:3001/`), inutilizzabile dall'interno dei container | il bot non raggiungerebbe il Gateway | `SAKURA_BOT_GATEWAY_URL` punta al nome interno del servizio |
| D | Spacebar vieta ai bot l'endpoint inviti | `POST /invites/{code}` → `{"code":20001,"message":"Bots cannot use this endpoint"}` | il bot crea la propria guild con `POST /guilds` |
| E | `guild.autoJoin` con `bots: true` non ha aggiunto il bot alla guild esistente | il bot non vede la guild | creazione della guild da parte del bot (punto D) |
| F | `POST /auth/login` con utente e password risponde `Invalid login or password` anche subito dopo la registrazione | impossibile rifare il login via REST | usare il token restituito dalla registrazione |
| G | `Embed.to_dict` serializza sempre `flags`; lo schema embed di Spacebar rifiuta la proprietà aggiuntiva | il comando viene eseguito ma la risposta muore con HTTP 400, codice 50035, `additionalProperties: flags` | `core/platform.py` rimuove `flags` dagli embed serializzati |
| H | Il callback dell'interazione risponde `204 No Content` anche con `with_response=1`, mentre discord.py legge `data['interaction']` | il messaggio viene recapitato ma poi arriva `TypeError: string indices must be integers` | `core/platform.py` riempie gli attributi con valori neutri quando il corpo non è un oggetto |
| I | Spacebar rifiuta il callback di defer (tipo 5) senza contenuto | HTTP 400, codice 50006, `Empty messages are not allowed`: ogni comando che fa `defer()` fallisce | `core/platform.py` salta il defer per gli application command e la risposta reale parte come risposta iniziale |
| J | Spacebar non implementa il webhook di followup delle interazioni | `POST /webhooks/{app_id}/{token}` → HTTP 404, codice 10015, `Unknown webhook` | `core/platform.py` reindirizza `interaction.followup` verso `interaction.response` |

Gli adattamenti A–J vivono in `sakura-bot/core/platform.py`, sono applicati
**solo** quando `SAKURA_BOT_PLATFORM=spacebar` e sono coperti da
`tests/unit/test_platform_config.py` e `tests/unit/test_spacebar_endpoints.py`
(i test `test_library_rejects_charset_suffix_without_the_adapter`,
`test_command_payload_sends_null_without_the_adapter`,
`test_embed_payload_keeps_flags_without_the_adapter` e
`test_callback_response_rejects_an_empty_body_without_the_adapter` documentano
il difetto originale della libreria).

## Comandi slash: registrazione e invocazione

| Comando | Registrato su Spacebar | Invocazione reale |
|---|---|---|
| `sakura-help` | PASS | **PASS** — embed `🌸 Sakura Spirit Bot - Help` |
| `sakura-server-info` | PASS | **PASS** — embed `🌸 Sakura Beta Guild` |
| `sakura-spirit-adopt` | PASS | **PASS** — embed `🎉 Spirit Companion Adopted!` |
| `sakura-my-spirit` | PASS | **PASS** — embed `🌸 Hanami` dopo l'adozione |
| `sakura-spirit-interact` | PASS | **PASS** — embed della risposta dello spirito |
| `sakura-weather` | PASS | **PASS** — embed `🌤️ Weather Change: Gentle Breeze` |
| `sakura-profile`, `sakura-admin-toggle-feature`, `sakura-admin-set-weather`, `sakura-admin-stats` | PASS | NOT_RUN |
| `sakura-spirit-info`, `sakura-weather-effects`, `sakura-weather-history`, `sakura-weather-list` | PASS | NOT_RUN |
| `sakura-send-gift`, `sakura-daily-dream`, `sakura-relationships` | PASS | NOT_RUN |
| `sakura-lfg`, `sakura-ritual-buff`, `sakura-game-stats` | PASS | NOT_RUN |
| `sakura-explore`, `sakura-shop`, `sakura-quests`, `sakura-map`, `sakura-inventory` | PASS | NOT_RUN |

Totale: **25 su 25 registrati** (verificato sia dal log del bot sia via REST) e
**6 su 25 invocati davvero**, scelti perché coprono i percorsi diversi: risposta
diretta, stato su database, AI locale, `defer()` e due cog differenti. Gli altri
19 comandi restano `NOT_RUN`: la registrazione è verificata, l'esecuzione no.

L'invocazione non richiede il client web: `scripts/spacebar_invoke_command.py`
invia lo stesso `POST /interactions` che manda il client, con un utente locale
usa-e-getta. Restano fuori da questa prova i comandi che richiedono permessi di
amministratore o di moderazione, che non sono stati forzati.

## Casi protocollari non ancora verificati

| Caso | Stato | Motivo |
|---|---|---|
| `interaction.response.send_message` | **PASS** | sei comandi hanno risposto nella risposta iniziale (adattamenti G e H) |
| `interaction.response.defer()` + `followup.send` | **PASS** (con adattamenti I e J) | il defer viene saltato e il followup reindirizzato: `sakura-spirit-adopt` e `sakura-spirit-interact` rispondono |
| Risposta `ephemeral=True` | NOT_RUN | l'unico ramo effimero del bot richiede un contesto DM: in guild nessun comando testato lo usa |
| Embed multipli e Unicode/emoji nella UI | PARZIALE | embed con emoji arrivano integri via REST; la resa grafica richiede il client |
| Autocomplete e validazione tipi argomenti | PARZIALE | un'opzione stringa (`message`) è stata passata e accettata; autocomplete non usato dal bot |
| `on_raw_reaction_add` | NOT_RUN | richiede un client che aggiunga reazioni |
| `on_voice_state_update` | NOT_RUN | richiede voice, non supportato dal server |
| Screenshot della GUI | NOT_RUN | il client (Fermi) non ha immagine Docker: va compilato da sorgente, procedura nel README |

## Funzionalità dichiarate non supportate da Spacebar

Dalla FAQ ufficiale (`docs.spacebar.chat/faq`), testuale: *"The big Discord.com
features currently left unimplemented or with partial implementations are:
Voice/Video support (WebRTC protocol support implemented, but lacking UDP
protocol implementation), Voice activities, OAuth2 scopes and other applications
(Bot applications work by are left unscoped), Message threads, Pomelo (new
username system without discriminators), Auto moderation"*.

Conseguenze per il bot:

| Funzionalità Spacebar | Impatto su Sakura |
|---|---|
| Voice/video senza UDP | `on_voice_state_update` e i comandi che lo usano non sono verificabili |
| Thread | nessun comando Sakura li usa oggi |
| OAuth2 senza scope | l'installazione del bot non passa da un flusso OAuth2 |
| Auto moderation | non usata dal bot |
| Pomelo assente | il bot mostra `username#discriminator`, non `@username` |

## Riproduzione delle verifiche

```powershell
# 1. Stack attivo e bot connesso.
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml ps

# 2. Spike del trasporto: REST, Gateway, READY, guild, messaggio, comandi.
.\.venv\Scripts\python.exe spacebar-beta\spike\discord_py_spike.py

# 3. Probe /health e /ready dall'interno dello stack.
Get-Content spacebar-beta\spike\probe.py -Raw | docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml exec -T sakura-bot-beta python -

# 4. Isolamento di rete.
Get-Content spacebar-beta\spike\egress_check.py -Raw | docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml exec -T sakura-bot-beta python -

# 5. AI mock.
Get-Content spacebar-beta\spike\ai_mock_check.py -Raw | docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml exec -T sakura-bot-beta python -

# 6. Comandi realmente registrati su Spacebar.
$token = ((Get-Content .env.spacebar | Select-String 'SPACEBAR_BOT_TOKEN=') -split '=',2)[1].Trim()
$appId = ((Get-Content .env.spacebar | Select-String 'SPACEBAR_BOT_CLIENT_ID=') -split '=',2)[1].Trim()
(Invoke-RestMethod -Uri "http://127.0.0.1:3002/api/v9/applications/$appId/commands" -Headers @{ Authorization = "Bot $token" }).Count

# 7. Invocazione reale di un comando, senza client web.
.\\.venv\\Scripts\\python.exe scripts\\spacebar_invoke_command.py sakura-help --new-user
.\\.venv\\Scripts\\python.exe scripts\\spacebar_invoke_command.py sakura-spirit-adopt --new-user
.\\.venv\\Scripts\\python.exe scripts\\spacebar_invoke_command.py sakura-my-spirit --new-user
.\\.venv\\Scripts\\python.exe scripts\\spacebar_invoke_command.py sakura-spirit-interact --new-user --option "message=Ciao spirito"
.\\.venv\\Scripts\\python.exe scripts\\spacebar_invoke_command.py sakura-server-info --new-user
.\\.venv\\Scripts\\python.exe scripts\\spacebar_invoke_command.py sakura-weather --new-user
```

Lo script stampa il numero di messaggi nuovi nel canale e, per ognuno, autore,
numero di embed e titoli: è l'evidenza che il comando è stato eseguito e che la
risposta è arrivata. Un comando effimero non lascia messaggi in cronologia, quindi
per quello l'evidenza è "nessun messaggio nuovo e nessun errore nel log del bot".

## Passo successivo: Discord staging (non eseguito)

La verifica end-to-end ufficiale resta su un server Discord reale dedicato allo
staging, con un'applicazione Discord di test separata:

1. Stesso codice e stessa immagine, `SAKURA_BOT_PLATFORM=discord` (nessun patch).
2. Token di un'applicazione Discord **diversa** da quella di produzione.
3. Database e variabili indipendenti da beta e produzione.
4. Ricontrollare i 25 comandi, i permessi, gli eventi Gateway, le reaction, il
   voice, i messaggi ephemeral e i rate limit.
5. Promuovere in produzione solo dopo questa verifica, con una check-list
   esplicita.

Nessuna di queste operazioni è stata eseguita: richiede autorizzazione separata
e credenziali reali.
