# Beta Discord reale — guida operativa (Windows / PowerShell)

Stack isolato che esegue il **codice reale** del bot contro **Discord vero**, ma
con un'**applicazione Discord di test** e un **server privato di test**. Serve a
verificare i comandi slash nel client Discord senza toccare token, guild, dati o
volumi della produzione.

## Cosa fa e cosa non fa

| Fa | Non fa |
|---|---|
| Avvia il bot con `SAKURA_BOT_ENVIRONMENT=discord-beta` sullo **stesso codice** di produzione | Non avvia, ferma o riconfigura lo stack di produzione |
| Usa un'applicazione Discord separata (token, client ID e guild propri) | Non riusa il token o il client ID operativi |
| Usa PostgreSQL e Redis beta dedicati, con volumi e reti propri | Non monta `.env`, volumi o reti di produzione |
| Registra i 25 comandi slash **solo** sulla guild di test | Non pubblica i comandi globalmente |
| Risponde con il provider AI `stub` deterministico, senza rete | Non chiama OpenAI per impostazione predefinita |
| Richiede Internet: parla con `discord.com` e con il Gateway reale | Non simula Discord (per quello esiste la beta Spacebar) |

Il bot beta **non pubblica porte**: la connessione al Gateway è in uscita e le
probe `/health` e `/ready` si leggono dall'interno dello stack.

## Prerequisiti

- Windows 10/11 con Docker Desktop e backend WSL2 attivo.
- Repository clonato e PowerShell aperto nella **cartella root del repository**
  (quella che contiene `docker-compose.yml`): tutti i comandi seguenti assumono
  questa directory di lavoro.
- Connessione Internet stabile: senza rete il bot non raggiunge Discord.
- Un account Discord con accesso al Discord Developer Portal.
- Spazio su disco ridotto: le immagini sono quelle già usate dalla produzione
  (`python:3.13-slim`, `postgres`, `redis`), circa 1 GB in totale.

## File coinvolti

| File | Ruolo |
|---|---|
| `docker-compose.discord-beta.yml` | Stack beta: `beta-bot`, `beta-postgres`, `beta-redis` |
| `.env.discord-beta.example` | Modello versionabile con i segnaposto |
| `.env.discord-beta` | Configurazione locale reale (**ignorata da Git**) |
| `sakura-bot/tests/unit/test_discord_beta_configuration.py` | Test che bloccano le regressioni di isolamento e di sync |

## Parte 1 — Preparazione manuale su Discord

Da eseguire una sola volta, nel browser, con l'account proprietario del server di
test. Le etichette del portale possono cambiare: se un nome non corrisponde,
cercare la voce equivalente nella sezione indicata.

1. Aprire il **Discord Developer Portal** e creare una **nuova applicazione**
   chiamata `Sakura Spirit Bot Beta`. Deve essere diversa da quella di
   produzione: token e client ID condivisi rendono i due bot indistinguibili.
2. Aprire **Bot**, creare il bot dell'applicazione e **copiare il token** in
   `.env.discord-beta` (campo `SAKURA_BETA_DISCORD_TOKEN`). Non incollarlo in
   chat, non salvarlo nel repository, non riutilizzare quello di produzione. Se
   viene esposto, rigenerarlo subito.
3. Nella pagina **General Information** annotare l'**Application ID** e
   scriverlo in `SAKURA_BETA_DISCORD_CLIENT_ID`.
4. Nella pagina **Bot**, sezione *Privileged Gateway Intents*, abilitare gli
   intent che il codice richiede: **Message Content**, **Server Members** e
   **Presence**. Senza di essi il bot si connette ma non riceve i messaggi e i
   comandi possono fallire.
5. Creare un **server Discord privato** dedicato ai test, senza membri né dati
   di produzione.
6. Nel client Discord abilitare *Impostazioni utente → Avanzate → Modalità
   sviluppatore*, poi con il tasto destro sul server di test scegliere **Copia ID
   server** e scriverlo in `SAKURA_BETA_TEST_GUILD_ID`.
7. Nella pagina **OAuth2 → URL Generator** selezionare gli scope `bot` e
   `applications.commands` e i permessi minimi: *View Channels*, *Send
   Messages*, *Embed Links*, *Read Message History*, *Add Reactions*. Aprire
   l'URL generato e invitare l'app **solo** nel server di test.
8. Completare `.env.discord-beta` con una password PostgreSQL beta propria
   (solo caratteri alfanumerici) e lasciare `SAKURA_BETA_AI_PROVIDER=stub`.
9. Non invitare il bot beta nei server operativi e non collegare il bot di
   produzione al server di test.
10. Per i test dei permessi servono due account **umani** normali: uno con
    permessi di amministratore e uno senza. Non usare token di account utente né
    self-bot.

## Parte 2 — Configurazione locale

```powershell
# 1. Creare il file locale dal modello (solo la prima volta).
Copy-Item .env.discord-beta.example .env.discord-beta

# 2. Compilare i segnaposto INSERISCI_* con i valori della beta.
notepad .env.discord-beta
```

Se un segnaposto resta invariato il bot non si connette: la validazione della
configurazione avviene prima del login e il processo termina con un errore
esplicito invece di tentare una connessione con credenziali finte.

## Parte 3 — Primo avvio

```powershell
# 3. Validare il Compose senza avviare container.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml config --quiet

# 4. Avviare SOLO la beta Discord.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml up -d --build

# 5. Stato dei tre servizi beta.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml ps

# 6. Log del bot beta.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml logs -f beta-bot
```

`-f docker-compose.discord-beta.yml` e `--env-file .env.discord-beta` sono
obbligatori: un `docker compose up` senza argomenti avvia lo stack di
produzione con il `.env` di produzione.

## Parte 4 — Verifica

```powershell
# Readiness dall'interno del container: nessuna porta è pubblicata sull'host.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml exec -T beta-bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready').read().decode())"
```

Risposta attesa, HTTP 200:

```json
{"status": "ready", "checks": {"discord": true, "bootstrap": true, "database": true, "cache": true, "extensions": true}}
```

- `/health` (HTTP 200) prova solo che il processo è vivo: **non** dimostra che
  Discord sia connesso.
- `/ready` richiede gateway connesso, bootstrap completato, PostgreSQL
  raggiungibile, Redis che risponde a `PING` e tutte le estensioni richieste
  caricate. HTTP 503 con i check a `false` indica quale parte manca.
- Nei log il bot deve stampare `Synced 25 slash commands` e
  `Sakura Spirit Bot is ready!`.
- Nel client Discord i comandi `sakura-*` devono comparire **nel solo server di
  test**. Se compaiono in altri server la sync è avvenuta globalmente: fermare
  subito la beta e verificare `SAKURA_BOT_ENVIRONMENT` e
  `SAKURA_BOT_TEST_GUILD_ID`.

## Parte 5 — Test funzionali nel client Discord

Eseguire i comandi nel canale del server di test e annotare l'esito. I nomi sono
quelli verificati da `sakura-bot/tests/smoke/test_command_registry.py`.

| Ambito | Comando | Verifica minima | Esito |
|---|---|---|---|
| Registro | `/sakura-help` | Comando visibile, embed di aiuto | DA ESEGUIRE |
| Utente | `/sakura-profile` | Profilo creato/letto nel PostgreSQL beta | DA ESEGUIRE |
| Server | `/sakura-server-info` | Nome e ID del server di test, non della produzione | DA ESEGUIRE |
| Meteo | `/sakura-weather` | Stato letto e persistito nel DB beta | DA ESEGUIRE |
| Spiriti | `/sakura-spirit-adopt` | Adozione con embed, riga in `user_spirits` | DA ESEGUIRE |
| Spiriti | `/sakura-my-spirit` | Lo spirito adottato viene riletto | DA ESEGUIRE |
| AI stub | `/sakura-spirit-interact` | Risposta deterministica, nessun log di rete | DA ESEGUIRE |
| Social | `/sakura-daily-dream` | Embed del sogno, riga in `daily_dreams` | DA ESEGUIRE |
| Social | `/sakura-send-gift` | Defer/followup corretti, valuta trasferita | DA ESEGUIRE |
| Gaming | `/sakura-lfg` | Sessione in Redis beta, reazioni gestite | DA ESEGUIRE |
| Permessi | `/sakura-admin-stats` | Negato a un utente non admin | DA ESEGUIRE |
| Permessi | `/sakura-admin-set-weather` | Consentito a un utente admin | DA ESEGUIRE |
| Errori | Parametri errati | Messaggio di errore, nessuna eccezione non gestita | DA ESEGUIRE |
| Visivo | Embed nei canali beta | Screenshot manuale opzionale (`Win + Shift + S`) | DA ESEGUIRE |

`gacha` e `events` **non** sono caricati dal bootstrap: i comandi relativi non
esistono e non vanno attesi in questa beta.

## Comandi quotidiani

```powershell
# Log del bot beta.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml logs -f beta-bot

# Riavviare solo il bot dopo una modifica al codice.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml up -d --build beta-bot

# Fermare la beta mantenendo i dati.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml down
```

## Reset del solo ambiente beta

Distruttivo: cancella i dati beta, mai quelli di produzione. Eseguire solo dopo
aver verificato il nome del progetto.

```powershell
# Il nome del progetto deve essere sakura-spirit-bot-discord-beta.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml ls

# Reset: container e volumi del solo progetto beta.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml down -v
```

## Problemi frequenti

| Sintomo | Causa probabile | Rimedio |
|---|---|---|
| `Invalid AI provider configuration` all'avvio | `SAKURA_BETA_AI_PROVIDER` diverso da `stub`/`openai` | Correggere il valore nel file locale |
| `SAKURA_BOT_TEST_GUILD_ID is required` | `SAKURA_BOT_ENVIRONMENT=discord-beta` senza guild ID | Compilare `SAKURA_BETA_TEST_GUILD_ID`; il bot si ferma invece di sincronizzare globalmente |
| `Improper token has been passed` | Token errato, rigenerato o di produzione | Copiare il token dell'app beta, senza spazi |
| Il bot è online ma non risponde ai comandi | Intent privilegiati non abilitati, oppure app invitata senza `applications.commands` | Abilitare gli intent e reinvitare l'app con gli scope corretti |
| I comandi non compaiono nel server | Sync su un'altra guild, oppure client non aggiornato | Verificare `SAKURA_BOT_TEST_GUILD_ID`, riavviare il bot, riaprire il client |
| `/ready` risponde 503 con `database: false` | PostgreSQL beta non pronto o password non valida | Controllare `ps` e i log di `beta-postgres` |
| `/ready` risponde 503 con `cache: false` | Redis beta non raggiungibile | Controllare lo stato di `beta-redis` |
| `/ready` risponde 503 con `discord: false` | Gateway non connesso (rete assente, token errato) | Controllare la connessione e i log del bot |
| `password authentication failed` su PostgreSQL | Password con caratteri speciali non codificati nella URL | Usare una password alfanumerica e ricreare il volume beta |

## Limiti noti di questa guida

- La preparazione dell'applicazione Discord è manuale: nessuno script crea app,
  token o guild.
- Il provider `stub` non verifica la qualità delle risposte AI reali: per quello
  serve `SAKURA_BETA_AI_PROVIDER=openai` con una chiave beta dedicata e
  un'autorizzazione esplicita.
- La resa grafica degli embed va valutata a occhio nel client: nessun test
  automatico copre il rendering.
- L'isolamento è garantito da progetto Compose, volumi, reti e credenziali
  distinti; non è un confine di sicurezza contro un operatore che copia a mano
  il token di produzione.
- I test online restano `NON ESEGUITO` finché non vengono inseriti i token beta e
  non viene data l'autorizzazione a collegarsi a Discord.
