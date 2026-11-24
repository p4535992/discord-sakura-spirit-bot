# Guida beta Discord — Windows

> Versione italiana. Il documento primario è
> [DISCORD_BETA_GUIDE_WINDOWS.md](DISCORD_BETA_GUIDE_WINDOWS.md).

Stack isolato che esegue il **codice reale** del bot contro **Discord vero**, ma
con un'**applicazione Discord di test** e un **server privato di test**. Serve a
verificare i comandi slash nel client Discord senza toccare token, guild, dati o
volumi della produzione.

## Livelli di test: da nessun Discord alla produzione

Il repository copre i primi due livelli, e ognuno risponde a una domanda diversa.

| Livello | Ambiente | Cosa dimostra | Dove |
|---|---|---|---|
| 0 | Nessun server | Logica e regressioni: configurazione, scope della sync, provider AI, isolamento dei file | `python -m pytest` nella cartella `sakura-bot` |
| 1 | **Spacebar self-hosted** | Trasporto: REST, Gateway, registrazione e **dispatch reale** dei comandi slash, con AI mock | `docs/SPACEBAR_BETA.md` |
| 2 | **Discord vero, guild privata** | Comportamento reale di Discord: permessi, intent privilegiati, resa degli embed, rate limit | questa guida |
| 3 | Produzione | Dati e carico reali | fuori scope |

Il livello 1 è l'"ambiente Discord" senza Discord: un server compatibile
self-hosted, nessun account Discord, nessun token reale, nessuna chiamata a
`discord.com` o a OpenAI. Non sostituisce il livello 2: Spacebar non riproduce i
permessi di Discord, la resa esatta degli embed, i limiti di rate né il Gateway
reale. Regola pratica: se il dubbio è "il comando funziona" si parte dal livello
1; se il dubbio è "su Discord si vede e si comporta bene" serve il livello 2.

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

## Parte 1 — Preparazione su Discord (manuale, una sola volta)

Tutta questa parte avviene nel browser, sul Discord Developer Portal e nel client
Discord. Nessuno script crea applicazioni, token o guild.

### 1.1 Creare l'applicazione beta

1. Accedere a Discord nel browser con l'account che sarà proprietario della beta.
2. Aprire <https://discord.com/developers/applications>.
3. **New Application** in alto a destra, nome `Sakura Spirit Bot (Beta)`,
   accettare i termini per sviluppatori e confermare con **Create**.
4. La beta è un'**applicazione separata**: stesso codice, identità diversa. È
   questo che rende innocuo per la produzione un errore o una fuga di token.

### 1.2 Copiare l'Application ID

1. Menu di sinistra → **General Information**.
2. Riga **Application ID** → **Copy**.

È il client ID che il bot invia quando si identifica, e va in
`SAKURA_BETA_DISCORD_CLIENT_ID`: una stringa numerica di 17-19 cifre. Non
confonderlo con **Public Key** o **Application Secret**: questo bot non li usa.

### 1.3 Generare e copiare il token del bot

1. Menu di sinistra → **Bot**.
2. Se non è mostrato alcun token, cliccare **Reset Token** → **Yes, do it!**. Il
   token viene mostrato **una sola volta**: copiarlo subito.
3. Incollarlo in `.env.discord-beta` sulla riga `SAKURA_BETA_DISCORD_TOKEN=`,
   senza virgolette, senza spazi e **senza il prefisso `Bot `** (lo aggiunge il
   codice).
4. Se il token viene perso, **Reset Token** ne genera uno nuovo e il vecchio
   smette di funzionare: aggiornare il file e riavviare lo stack.

Mai committarlo, mai incollarlo in una chat o in un ticket, mai includerlo in uno
screenshot, mai riusare il token di produzione, mai inserirlo in un'immagine.

### 1.4 Abilitare i tre intent privilegiati

Sempre nella pagina **Bot**, sezione **Privileged Gateway Intents**:

| Interruttore | Necessario | Perché |
|---|---|---|
| **Presence Intent** | sì | `core/bot.py` richiede `intents.presences` |
| **Server Members Intent** | sì | `core/bot.py` richiede `intents.members` |
| **Message Content Intent** | sì | `core/bot.py` richiede `intents.message_content` |

Cliccare **Save Changes**. `intents.voice_states` è richiesto anch'esso, ma non è
un intent privilegiato e non ha interruttore.

Senza questi interruttori il login fallisce con `PrivilegedIntentsRequired`
(codice di chiusura Gateway `4014`, "Disallowed intent(s)"), anche con un token
valido. Sotto le 100 guild non serve la verifica del bot, quindi le modifiche
hanno effetto al login successivo.

### 1.5 Creare la guild privata di test

1. Nel client Discord cliccare **+** in fondo alla lista dei server.
2. **Create My Own** → **For me and my friends**.
3. Dare un nome, per esempio `Sakura Beta Test`, e confermare.

Tenerla privata: nessuna discovery pubblica e nessun invito a estranei. Poiché la
sync è limitata alla guild, i comandi esistono solo qui.

### 1.6 Copiare l'ID della guild

1. Abilitare la Modalità sviluppatore: **Impostazioni utente** → **Avanzate** →
   **Modalità sviluppatore**.
2. Tasto destro sull'icona del server → **Copia ID server**.
3. Incollarlo in `SAKURA_BETA_TEST_GUILD_ID` (17-19 cifre).

Opzionale: tasto destro sul proprio avatar → **Copia ID utente** e inserirlo in
`SAKURA_BETA_OWNER_ID`. Il bot parte anche senza; la variabile identifica solo
l'account proprietario.

### 1.7 Invitare il bot nella guild di test

1. Menu di sinistra → **OAuth2** → **URL Generator**.
2. Scope: **`bot`** e **`applications.commands`**. Il secondo è obbligatorio:
   senza di esso i comandi slash non possono essere registrati e il bot sembra
   online ma nessun comando compare.
3. Permessi del bot (minimo necessario per questo bot): **View Channels**,
   **Send Messages**, **Embed Links**, **Read Message History**,
   **Add Reactions**, **Use Application Commands**.
4. Copiare l'URL generato, aprirlo nel browser, selezionare la guild di **test** e
   cliccare **Authorize**.

Il bot compare nella lista membri come offline finché lo stack non viene avviato.
Tre comandi admin sono dichiarati con `default_permissions(administrator=True)`:
per provarli concedere **Administrator** nella guild di test (accettabile lì),
oppure verificare solo il percorso di rifiuto con un account normale.

### 1.8 Compilare `.env.discord-beta`

```powershell
Copy-Item .env.discord-beta.example .env.discord-beta
notepad .env.discord-beta
```

| Variabile | Da dove arriva il valore | Formato |
|---|---|---|
| `SAKURA_BETA_DISCORD_TOKEN` | Bot → **Reset Token** | tre parti separate da punti |
| `SAKURA_BETA_DISCORD_CLIENT_ID` | General Information → **Application ID** | 17-19 cifre |
| `SAKURA_BETA_TEST_GUILD_ID` | tasto destro sul server → **Copia ID server** | 17-19 cifre |
| `SAKURA_BETA_OWNER_ID` | tasto destro sull'avatar → **Copia ID utente** | opzionale, 17-19 cifre |
| `SAKURA_BETA_POSTGRES_PASSWORD` | scelta propria | solo alfanumerica |
| `SAKURA_BETA_AI_PROVIDER` | `stub` (default) oppure `openai` | `stub` non richiede chiave |
| `SAKURA_BETA_OPENAI_API_KEY` | solo con `openai` | chiave beta dedicata |

Ogni segnaposto `INSERISCI_*` e `CAMBIA_*` va sostituito: il bot rifiuta i valori
del modello prima del login invece di connettersi con credenziali finte. La
password del database deve essere alfanumerica, perché viene inserita nella URL
SQLAlchemy senza escaping (`@ : / #` la romperebbero).

### 1.9 Igiene del token

- L'applicazione beta è usa e getta: **Reset Token** revoca l'accesso senza
  toccare la produzione.
- Se il token trapela: reset, aggiornamento di `.env.discord-beta`, riavvio, poi
  controllo del registro di audit della guild per azioni inattese.
- `.env.discord-beta` è coperto da `.gitignore`; non copiarlo mai in un'immagine e
  non montarlo in uno stack diverso da quello beta.

## Parte 2 — Configurazione locale

Il file si crea e si compila in [1.8](#18-compilare-envdiscord-beta). Validarlo
senza avviare nulla:

```powershell
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml config --quiet
```

Output vuoto e codice di uscita `0` significano che il file è completo: tutte le
variabili richieste sono presenti (`:?` nel file Compose fallisce altrimenti) e
l'interpolazione è valida. Se un segnaposto è rimasto il comando riesce comunque,
ma il bot non parte: la validazione della configurazione avviene prima del login
e il processo termina con un errore esplicito invece di tentare una connessione
con credenziali finte.

## Parte 3 — Primo avvio

```powershell
# Avviare SOLO la beta Discord.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml up -d --build

# Stato dei tre servizi beta.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml ps

# Log del bot beta.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml logs -f beta-bot
```

`-f docker-compose.discord-beta.yml` e `--env-file .env.discord-beta` sono
obbligatori: un `docker compose up` senza argomenti avvia lo stack di produzione
con il `.env` di produzione.

Righe attese nei log, in questo ordine:

```text
Loaded extension: commands.spirit_commands
...
Synced 25 slash commands
Sakura Spirit Bot is ready!
```

`Synced 25 slash commands` dimostra che il caricamento è avvenuto sulla guild: i
comandi ora sono nel solo server di test.

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
  caricate. HTTP 503 con un check a `false` indica quale parte manca.
- Nel client Discord i comandi `sakura-*` devono comparire **nel solo server di
  test**. Se compaiono in altri server la sync è avvenuta globalmente: fermare
  subito la beta e verificare `SAKURA_BOT_ENVIRONMENT` e
  `SAKURA_BOT_TEST_GUILD_ID`.

## Parte 5 — Test funzionali nel client Discord

Eseguire i comandi in un canale della guild di test e annotare l'esito. I nomi
sono quelli verificati da `sakura-bot/tests/smoke/test_command_registry.py`.

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

Le righe sui permessi richiedono **due account umani** normali: uno con permessi
di amministratore e uno senza. Non usare token di account utente né self-bot.

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
| `Replace the .env template placeholders before starting: ...` | Un valore `INSERISCI_*` è rimasto in `.env.discord-beta` | Compilare le variabili elencate e riavviare |
| `Invalid AI provider configuration` all'avvio | `SAKURA_BETA_AI_PROVIDER` diverso da `stub`/`openai` | Correggere il valore nel file locale |
| `SAKURA_BOT_TEST_GUILD_ID is required` | `SAKURA_BOT_ENVIRONMENT=discord-beta` senza guild ID | Compilare `SAKURA_BETA_TEST_GUILD_ID`; il bot si ferma invece di sincronizzare globalmente |
| `PrivilegedIntentsRequired`, codice Gateway `4014` | Uno dei tre intent privilegiati è spento | Abilitare Presence, Server Members e Message Content, poi riavviare |
| `Improper token has been passed` | Token errato, rigenerato o di produzione | Copiare il token dell'app beta, senza spazi né prefisso `Bot ` |
| Il bot è online ma non risponde ai comandi | Intent privilegiati non abilitati, oppure app invitata senza `applications.commands` | Abilitare gli intent e reinvitare l'app con gli scope corretti |
| I comandi non compaiono nel server | Sync su un'altra guild, oppure cache del client | Verificare `SAKURA_BETA_TEST_GUILD_ID`, riavviare il bot, riaprire il client |
| I comandi compaiono in altri server | La sync è avvenuta globalmente | Fermare la beta e verificare `SAKURA_BOT_ENVIRONMENT` e `SAKURA_BOT_TEST_GUILD_ID` |
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
- I test online restano `NON ESEGUITO` finché non vengono inserite le credenziali
  beta e non viene data l'autorizzazione a collegarsi a Discord.
