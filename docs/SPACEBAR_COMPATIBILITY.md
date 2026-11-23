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

## Incompatibilità reali trovate (e adattate)

| # | Problema | Effetto senza adattamento | Adattamento |
|---|---|---|---|
| A | Spacebar risponde `application/json; charset=utf-8`, discord.py confronta `content-type == 'application/json'` per uguaglianza esatta | ogni risposta torna come stringa: `TypeError: string indices must be integers` durante il login | `core/platform.py` sostituisce `discord.http.json_or_text` |
| B | discord.py invia `contexts`/`integration_types` a `null`; lo schema Spacebar richiede array | `CommandSyncFailure` HTTP 400, codice 50035, `must be array` | `core/platform.py` fa restituire `[]` a `_merge_to_array` |
| C | `GET /gateway/bot` restituisce l'endpoint **pubblico** (`ws://127.0.0.1:3001/`), inutilizzabile dall'interno dei container | il bot non raggiungerebbe il Gateway | `SAKURA_BOT_GATEWAY_URL` punta al nome interno del servizio |
| D | Spacebar vieta ai bot l'endpoint inviti | `POST /invites/{code}` → `{"code":20001,"message":"Bots cannot use this endpoint"}` | il bot crea la propria guild con `POST /guilds` |
| E | `guild.autoJoin` con `bots: true` non ha aggiunto il bot alla guild esistente | il bot non vede la guild | creazione della guild da parte del bot (punto D) |
| F | `POST /auth/login` con utente e password risponde `Invalid login or password` anche subito dopo la registrazione | impossibile rifare il login via REST | usare il token restituito dalla registrazione |

Gli adattamenti A e B vivono in `sakura-bot/core/platform.py`, sono applicati
**solo** quando `SAKURA_BOT_PLATFORM=spacebar` e sono coperti da
`tests/unit/test_platform_config.py` e `tests/unit/test_spacebar_endpoints.py`
(il test `test_library_rejects_charset_suffix_without_the_adapter` documenta il
difetto originale della libreria).

## Comandi slash: registrazione e invocazione

| Comando | Registrato su Spacebar | Invocazione reale |
|---|---|---|
| `sakura-help`, `sakura-profile`, `sakura-server-info` | PASS | NOT_RUN |
| `sakura-admin-toggle-feature`, `sakura-admin-set-weather`, `sakura-admin-stats` | PASS | NOT_RUN |
| `sakura-my-spirit`, `sakura-spirit-info`, `sakura-spirit-adopt`, `sakura-spirit-interact` | PASS | NOT_RUN |
| `sakura-weather`, `sakura-weather-effects`, `sakura-weather-history`, `sakura-weather-list` | PASS | NOT_RUN |
| `sakura-send-gift`, `sakura-daily-dream`, `sakura-relationships` | PASS | NOT_RUN |
| `sakura-lfg`, `sakura-ritual-buff`, `sakura-game-stats` | PASS | NOT_RUN |
| `sakura-explore`, `sakura-shop`, `sakura-quests`, `sakura-map`, `sakura-inventory` | PASS | NOT_RUN |

Totale: **25 su 25 registrati** (verificato sia dal log del bot sia via REST).
L'invocazione reale richiede un client che invii l'interazione: senza client web
non è stata eseguita e **non** viene dichiarata superata.

## Casi protocollari non ancora verificati

| Caso | Stato | Motivo |
|---|---|---|
| `interaction.response.send_message` | NOT_RUN | serve un client che invii l'interazione |
| `interaction.response.defer()` + `followup.send` | NOT_RUN | idem |
| Risposta `ephemeral=True` | NOT_RUN | idem |
| Embed multipli e Unicode/emoji nella UI | NOT_RUN | idem |
| Autocomplete e validazione tipi argomenti | NOT_RUN | idem |
| `on_raw_reaction_add` | NOT_RUN | richiede un client che aggiunga reazioni |
| `on_voice_state_update` | NOT_RUN | richiede voice, non supportato dal server |
| Screenshot della GUI | NOT_RUN | client web non disponibile come immagine |

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
```

## Passo successivo: Discord staging (non eseguito)

La verifica end-to-end ufficiale resta su un server Discord reale dedicato allo
staging, con un'applicazione Discord di test separata:

1. Stesso codice e stessa immagine, `SAKURA_BOT_PLATFORM=discord` (nessun patch).
2. Token di un'applicazione Discord **diversa** da quella di produzione.
3. Database, Redis e variabili indipendenti da beta e produzione.
4. Ricontrollare i 25 comandi, i permessi, gli eventi Gateway, le reaction, il
   voice, i messaggi ephemeral e i rate limit.
5. Promuovere in produzione solo dopo questa verifica, con una check-list
   esplicita.

Nessuna di queste operazioni è stata eseguita: richiede autorizzazione separata
e credenziali reali.
