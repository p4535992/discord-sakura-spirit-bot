# Mapping sorgente — `RPG Weather Dnd5e.xlsx`

Mappatura cella → campo → unità → conversione del workbook storico dei climi,
verificata sul clone locale alla revisione `acf29923d97aef786678348bc634daddf48f9b16`
(branch `main`). Il documento è la base della Fase A della specifica meteo e
accompagna il catalogo versionato
`sakura-bot/systems/weather/climate_catalog.json`.

Il file `.xlsx` **è versionato nel repository**, in `docs/xlsx/RPG Weather Dnd5e.xlsx`
(324.931 byte, SHA-256 `accc79fb…098515`): il catalogo viene generato con
`scripts/extract_weather_workbook.py` e il JSON risultante è l'artefatto che i
test e il codice leggono a runtime. Il workbook resta la fonte verificabile per
ricontrollare la mappatura, non un input del motore.

## Stato della verifica

| Attività | Stato | Evidenza |
|---|---|---|
| Lettura dei cinque fogli e dei valori memorizzati | PASS | estrattore stdlib, 12 climi × 12 mesi, 13 classi di vento, 996 righe |
| Matrice 12×12 delle probabilità di precipitazione | PASS | `tests/unit/test_weather_catalog.py`, confronto con `Climates` |
| Conversioni °F→°C e mph→km/h | PASS | test sul catalogo, tolleranza dichiarata |
| Coerenza `cold <= avg <= hot` | PASS | test su tutte le 144 combinazioni clima/mese |
| Esecuzione del bot o scrittura su database | NON ESEGUITO | nessun container avviato in questa sessione |
| Verifica su Discord beta o Spacebar | NON ESEGUITO | richiede credenziali reali |

## Il workbook non è un motore runtime

Tre motivi, tutti verificati leggendo le formule memorizzate:

1. Decine di celle usano `RANDBETWEEN`: ogni ricalcolo del foglio produce valori
   nuovi. La nota `Settings!L3` lo dice esplicitamente — *«Every alteration to
   the document randomizes the weather again»*.
2. Alcune formule di Google Sheets sono arrivate nell'XLSX come
   `__xludf.DUMMYFUNCTION(...)` con un valore di fallback: sono leggibili come
   traccia dell'intenzione, non come calcolo eseguibile.
3. Non esiste alcun concetto di canale, stato persistente o riavvio: il foglio
   genera un anno in memoria e lo perde.

Il catalogo distingue perciò due categorie, dichiarate nel campo `stability`:

| Categoria | Contenuto | Uso consentito |
|---|---|---|
| `static` | probabilità mensili, classi di vento, vocabolari di pioggia/neve/nuvole/fenomeni/direzioni | dati di riferimento del motore |
| `randomized_snapshot` | `temp_f`, `cold_f`, `avg_f`, `hot_f` e i conteggi osservati di vento/direzione/fenomeni | solo evidenza di un ricalcolo, mai normali climatiche |

## Foglio `Settings`

| Cella | Campo | Valore letto | Unità | Note |
|---|---|---|---|---|
| `A1`, `A2:A13` | nomi dei mesi | January … December | — | intestazione + 12 mesi |
| `B2:B13` | giorni per mese | 31, 28, 31, 30, … | giorni | anno non bisestile |
| `D2` | clima selezionato | `Cool and Rainy` | — | cella di lavoro del foglio |
| `E2` | latitudine | 50 | gradi | usata dalla correzione di `Temp` |
| `D4:D15` | elenco dei 12 climi | Desert … Polar | — | etichette pubbliche |
| `E4:E15` | latitudini tipiche | `0–30°`, `70°+`, … | gradi | testo descrittivo |
| `D17` / `D18` | unità di temperatura | `Temperature Units` / `Celsius` | — | intestazione e valore |
| `E17` / `E18` | punto di congelamento | `Freezing` / `0` | °C | usato per pioggia/neve |
| `D19` / `E19` | *Temp outer bound* | 7 | °C | escursione massima dal riferimento |
| `D20` / `E20` | *Temp inner bound* | 2 | °C | escursione minima dal riferimento |
| `D22` / `E22` | nebbia con pioggia | 0,15 | probabilità | condizionata all'evento piovoso |
| `D23` / `E23` | fulmini con tempesta | 0,25 | probabilità | condizionata |
| `D24` / `E24` | grandine con pioggia | 0,10 | probabilità | condizionata |
| `D25` / `E25` | grandine con tempesta | 0,20 | probabilità | condizionata |
| `G2` | `Precip` del mese selezionato | 0,35 | probabilità | formula `FILTER` su `Climates` |
| `H2:H13` | `Temp` del mese selezionato | −4 … 26 | °C | `IF($D$18="Fahrenheit",I,J)` |
| `I2:I13` | temperatura in °F | 25 … 79 | °F | `FILTER` su `Climates` |
| `J2:J13` | temperatura in °C | −4 … 26 | °C | `ROUND((I-32)*(5/9),0)` |
| `L3` | note di progetto | testo | — | fonte *Dragon Magazine* #137 |

I valori di `H`, `I`, `J` dipendono dal clima scelto in `D2` e cambiano se
l'utente cambia clima: non sono costanti del file.

## Foglio `Climates`

Struttura verificata:

- riga 1: nome del clima ripetuto su **6 colonne consecutive** per ciascuno dei
  12 climi (da `D` a `BW`);
- riga 2: sotto-intestazioni `Temp`, `Cold`, `Avg`, `Hot`, `Precip` a partire
  dalla seconda colonna di ogni blocco;
- colonna `A`: estrazione `d100` usata dalle formule;
- colonna `B`: indice del mese (1…12);
- colonna `C`: nome del mese (`INDIRECT("Settings!A"&(ROW()-1))`);
- righe 3…14: i dodici mesi;
- colonna `D` di ogni blocco: etichetta descrittiva (`Cold winter:`, `Cold summer:`).

Blocchi individuati:

| Clima | Colonne | Cella nome |
|---|---|---|
| Desert | `D:I` | `Climates!D1` |
| Tropical Savanna | `J:O` | `Climates!J1` |
| Steppes | `P:U` | `Climates!P1` |
| Equatorial | `V:AA` | `Climates!V1` |
| Monsoon | `AB:AG` | `Climates!AB1` |
| Warm and Rainy | `AH:AM` | `Climates!AH1` |
| Warm with Dry Summer | `AN:AS` | `Climates!AN1` |
| Warm with Dry Winter | `AT:AY` | `Climates!AT1` |
| Cool and Rainy | `AZ:BE` | `Climates!AZ1` |
| Cool with Dry Winter | `BF:BK` | `Climates!BF1` |
| Tundra | `BL:BQ` | `Climates!BL1` |
| Polar | `BR:BW` | `Climates!BR1` |

### Matrice delle probabilità di precipitazione

Valori letti dalla colonna `Precip` di ogni blocco (righe 3…14), espressi in
percentuale. Sono **probabilità che il giorno sia piovoso/nevoso**, non
l'intensità della precipitazione.

| Clima | Gen | Feb | Mar | Apr | Mag | Giu | Lug | Ago | Set | Ott | Nov | Dic |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Desert | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| Tropical Savanna | 10 | 10 | 10 | 35 | 85 | 85 | 85 | 85 | 85 | 35 | 10 | 10 |
| Steppes | 20 | 20 | 20 | 20 | 20 | 20 | 5 | 5 | 5 | 20 | 20 | 20 |
| Equatorial | 30 | 30 | 50 | 50 | 50 | 40 | 40 | 40 | 40 | 40 | 40 | 40 |
| Monsoon | 15 | 15 | 15 | 15 | 15 | 90 | 90 | 90 | 90 | 90 | 15 | 15 |
| Warm and Rainy | 40 | 40 | 40 | 40 | 40 | 40 | 40 | 40 | 40 | 40 | 40 | 40 |
| Warm with Dry Summer | 30 | 30 | 30 | 30 | 30 | 10 | 10 | 10 | 30 | 30 | 30 | 30 |
| Warm with Dry Winter | 15 | 15 | 15 | 15 | 15 | 15 | 45 | 45 | 15 | 15 | 15 | 15 |
| Cool and Rainy | 35 | 35 | 35 | 35 | 35 | 35 | 35 | 35 | 35 | 35 | 35 | 35 |
| Cool with Dry Winter | 10 | 10 | 10 | 10 | 20 | 20 | 35 | 35 | 35 | 20 | 10 | 10 |
| Tundra | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| Polar | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 |

La matrice è **statica**: le formule sono funzioni deterministiche dell'indice
di mese, quindi riproducibili. È verificata riga per riga da
`test_precipitation_matrix_matches_the_workbook`.

### Temperature: cosa è stabile e cosa no

`Cold`, `Avg` e `Hot` sono in **°F** e derivano da `RANDBETWEEN`:

- `Cold` = `RANDBETWEEN(riferimento − 5, riferimento + 5)`;
- `Hot` = `RANDBETWEEN(riferimento − 5, riferimento + 5)`;
- `Avg` = `ROUND(AVERAGE(Cold, Hot), 0)`.

I riferimenti sono celle di parametro dello stesso blocco, quindi i valori
cambiano a ogni ricalcolo del foglio. Il catalogo li registra come
`randomized_snapshot`; i valori correnti (Desert gennaio `57 / 64 / 71`,
Desert luglio `65 / 88 / 110`) coincidono con quelli citati nella specifica, ma
restano la fotografia di un ricalcolo.

La colonna `Temp` **non** è una media climatica indipendente: è derivata dalle
tre precedenti più una correzione di latitudine. Per Desert gennaio:

```text
Temp = IF(d100 <= 5, Cold, IF(d100 > 95, Hot, Avg)) + ROUND((15 - latitudine) / 2, 0)
     = 64 + ROUND((15 - 50) / 2, 0) = 64 - 18 = 46 °F
```

Le altre famiglie di climi usano divisori diversi nella correzione
(`(35 − lat) / 3`, `(10 − lat) / 3`, `(30 − lat) / 3`, `(55 − lat) / 3`,
`(60 − lat) / 3`, `(70 − lat) / 3`), quindi `Temp` non è confrontabile fra climi
senza conoscere la formula del blocco.

**Scelta di progetto documentata:** il nuovo motore usa `avg_c` come valore di
riferimento giornaliero e `cold_c`/`hot_c` come inviluppo, invece di estrarre un
`Temp` casuale tra i tre. La deviazione è deliberata: rende il riferimento
stabile, verificabile e indipendente dalla latitudine configurata, e mantiene
comunque la relazione `cold <= avg <= hot` verificata dai test.

## Foglio `Wind`

Tredici classi, righe 2…14. La colonna `Chance` **non è una probabilità 0–100**:
è la soglia di un `VLOOKUP(..., TRUE)` applicato a un indice `RANDBETWEEN(1,n)*10`
che vale 10…200. Serve a distribuire i venti in modo non uniforme, non a
esprimere una percentuale.

| # | Classe | mph | km/h | Soglia `Chance` |
|---:|---|---|---:|---:|
| 1 | Calm | < 1 | 0,0–1,6 | 10 |
| 2 | Light air | 1–3 | 1,6–4,8 | 20 |
| 3 | Light breeze | 4–7 | 6,4–11,3 | 40 |
| 4 | Gentle breeze | 8–12 | 12,9–19,3 | 60 |
| 5 | Moderate breeze | 13–18 | 20,9–29,0 | 80 |
| 6 | Fresh breeze | 19–24 | 30,6–38,6 | 100 |
| 7 | Strong breeze | 25–31 | 40,2–49,9 | 120 |
| 8 | Moderate gale | 32–38 | 51,5–61,2 | 140 |
| 9 | Fresh gale | 39–46 | 62,8–74,0 | 160 |
| 10 | Strong gale | 47–54 | 75,6–86,9 | 170 |
| 11 | Storm | 55–63 | 88,5–101,4 | 180 |
| 12 | Violent storm | 64–72 | 103,0–115,9 | 190 |
| 13 | Hurricane | 73–136 | 117,5–218,9 | 198 |

Conversione applicata: `1 mph = 1,609344 km/h`. Gli intervalli sono convertiti
in coppie numeriche (`<1` → `0,00–0,99`) e verificati come ordinati e non
sovrapposti da `test_wind_classes_are_ordered_and_do_not_overlap`.

Le descrizioni inglesi della colonna `D` sono conservate nel catalogo come
`description` e non sono tradotte: sono testo sorgente, non etichette di UI.

## Foglio `Precipitation`

Colonne: `A` pioggia, `B` neve, `C` nuvole, `D` fenomeno, `E` vento, `F` mph,
`G` direzione, `H` descrizione del vento, `I` indice del vento. Righe dati 2…997,
**996 righe** effettive.

### Vocabolari (statici)

| Colonna | Valori | Righe per valore |
|---|---|---:|
| `A` pioggia | Light mist, Drizzle, Steady rainfall, Strong rainfall, Pounding rain, Downpour | 166 ciascuno |
| `B` neve | A few flakes, Dusting of snow, Flurries, Moderate snowfall, Heavy snowfall, Blizzard | 166 ciascuno |
| `C` nuvole | A few clouds, Mostly cloudy, Gray slightly overcast, Gray highly overcast, Dark storm clouds | 166, tranne Dark storm clouds = 332 |
| `D` fenomeni | Fog, Lightning, Hail, `Lightning, hail` | 220 righe non vuote su 996 |
| `G` direzioni | N, NE, E, SE, S, SW, W, NW | 116–138 ciascuna |

I vocabolari sono testo statico e quindi affidabili. Le **frequenze** delle
colonne `D`, `E`, `F`, `G`, `H`, `I` derivano invece da `RANDBETWEEN` e sono
registrate solo come `observed_counts`.

### Perché non si possono copiare le frequenze

Le colonne `E`, `F`, `H` sono `VLOOKUP` sulla colonna `I`, e `I` è
`RANDBETWEEN(1,n)*10`: la distribuzione del vento cambia a ogni ricalcolo. La
colonna `D` è `IF(RANDBETWEEN(1,100) <= Settings!$E$22*100, "Fog", "")` e simili:
anche i fenomeni sono ricampionati. La colonna `G` è
`CHOOSE(RANDBETWEEN(1,8), "N", "NE", ...)`: le otto direzioni sono uniformi per
costruzione, non per osservazione.

Conseguenza: le frequenze di vento, direzione e fenomeni del nuovo motore sono
**default di progetto** da validare con simulazione Monte Carlo, non dati Excel.

## Foglio `Year of Weather`

Colonne: `A` mese, `B` giorno, `C` minima, `D` massima, `E` precipitazione,
`F` nuvole, `G` fenomeno, `H` vento, `I` mph, `J` direzione, `K` descrizione,
`L` indice riga di `Precipitation`, `M` flag precipitazione, `N` temperatura del
mese, `O` temperatura del mese successivo, `P` riferimento aggiustato,
`Q` lunghezza del mese. Righe 2…1001 (1000 giorni).

È il foglio che rivela l'algoritmo effettivo, ricostruito dalle formule:

| Passo | Formula | Significato |
|---|---|---|
| 1 | `N2 = VLOOKUP(mese, Settings!A:H, 8, FALSE)` | temperatura di riferimento del mese |
| 2 | `O2 = Settings!H(mese+1)` | riferimento del mese successivo |
| 3 | `P2 = IF(giorno > 2*Q/3, P1 + ROUND((O2-N2)/(Q/3), 0), N2)` | deriva graduale verso il mese successivo nell'ultimo terzo |
| 4 | `M2 = RANDBETWEEN(1,100) <= Precip(mese)*100` | decide se il giorno è piovoso |
| 5 | `C2 = RANDBETWEEN(P2 - 7, P2 - 2)` | minima = riferimento − *outer bound* … − *inner bound* |
| 6 | `D2 = RANDBETWEEN(P2 + 2, P2 + 7)` | massima = riferimento + *inner bound* … + *outer bound* |
| 7 | `E2 = IF(M2, IF(AVERAGE(C2,D2) > 0, Precipitation!A, Precipitation!B), "None")` | pioggia o neve in base alla **media** di minima e massima rispetto a 0 °C |
| 8 | `F2 = IF(M2, Precipitation!C, CHOOSE(RANDBETWEEN(1,4), "Clear","Clear","A few clouds","Mostly cloudy"))` | nuvole dalla riga estratta, oppure cielo asciutto |
| 9 | `G2 = IF(AND(M2, AVERAGE(C2,D2) > 0), Precipitation!D, "")` | il fenomeno compare solo con precipitazione **liquida** |
| 10 | `L2 = RANDBETWEEN(2, COUNTA(Precipitation!A:A))` | riga 2…997 di `Precipitation` |

Due conseguenze importanti:

- minima e massima sono **correlate** al riferimento e non estratte in modo
  indipendente, come richiesto dalla specifica;
- la scelta pioggia/neve usa la media di minima e massima, non la minima: un
  giorno con media sotto 0 °C produce neve anche con massima positiva.

Il foglio **non** decide pioggia o neve leggendo le due colonne `A` e `B` di
`Precipitation` in modo indipendente: estrae una riga e poi sceglie una delle
due colonne in base alla temperatura. Le colonne `A` e `B` contengono quindi due
descrizioni alternative della stessa riga, non due eventi separati.

La distribuzione del cielo asciutto è ricavata dalla formula `CHOOSE`:
`Clear` 2/4, `A few clouds` 1/4, `Mostly cloudy` 1/4. È registrata in
`settings.clear_sky_choices` e verificata da
`test_clear_sky_distribution_is_recovered`.

## Campi non presenti nel workbook

Questi parametri servono al motore ma **non esistono** nel file: vanno trattati
come `project_default`, mai attribuiti all'Excel.

| Parametro | Stato | Fonte |
|---|---|---|
| Umidità minima/massima per mese | assente | default di progetto |
| Raffiche e relazione raffica/vento medio | assente | default di progetto |
| Visibilità | assente | default di progetto |
| Pressione | assente | default di progetto |
| Pesi delle direzioni del vento | assente (uniforme per costruzione) | default di progetto |
| Probabilità degli eventi speciali | assente | default di progetto |
| Retention di storico, tick ed eventi | assente | default di progetto |
| Quote di immagini e metadati | assente | default di progetto |

Nella specifica questi campi sono già marcati come aggiunte; il catalogo non li
contiene e il codice non deve leggerli da qui.

## Conversioni applicate

| Da | A | Formula | Dove |
|---|---|---|---|
| °F | °C | `(F - 32) * 5 / 9` | `cold_c`, `avg_c`, `hot_c` |
| mph | km/h | `mph * 1,609344` | `kmh_min`, `kmh_max` |
| frazione | percentuale | `* 100` | `precipitation_probability_pct` |

I valori in °C sono arrotondati a una cifra decimale; i test usano una
tolleranza di 0,05 °C per non dipendere dall'arrotondamento.

## Rigenerare il catalogo

Dalla radice del repository, con il workbook versionato nel progetto:

```powershell
.\.venv\Scripts\python.exe scripts\extract_weather_workbook.py --source "docs\xlsx\RPG Weather Dnd5e.xlsx"
```

Lo script usa solo la libreria standard, non richiede `openpyxl` e scrive
`sakura-bot/systems/weather/climate_catalog.json`. Il percorso di output è
sovrascrivibile con `--output`.

Il catalogo sta accanto al motore e non sotto una directory `data/`: il
`.gitignore` del repository esclude `**/data/**` perché la riserva al runtime dei
container, mentre questo file è un dato di riferimento versionato.

Il catalogo registra `source.sha256` e `source.size_bytes`: se il workbook cambia,
il digest cambia e il confronto con i test rende visibile la differenza.

## Copertura dei test

| Test | Cosa verifica |
|---|---|
| `test_catalog_declares_its_source` | foglio di origine, digest, elenco dei cinque fogli |
| `test_twelve_climates_with_twelve_months` | 12 climi, 12 mesi, ordine gennaio→dicembre |
| `test_precipitation_matrix_matches_the_workbook` | la matrice 12×12 riga per riga |
| `test_precipitation_probability_is_also_stored_as_a_fraction` | coerenza frazione/percentuale |
| `test_temperature_references_are_ordered` | `cold <= avg <= hot` in °F e °C |
| `test_temperature_references_convert_from_fahrenheit` | conversione °F→°C |
| `test_wind_classes_are_ordered_and_do_not_overlap` | 13 classi, intervalli crescenti e disgiunti |
| `test_wind_classes_convert_to_kmh` | conversione mph→km/h |
| `test_wind_lookup_thresholds_are_not_probabilities` | `Chance` è una soglia, non una percentuale |
| `test_precipitation_vocabularies` | vocabolari di pioggia, neve, nuvole, fenomeni, direzioni |
| `test_precipitation_sheet_shape` | 996 righe, 166 per intensità |
| `test_settings_match_the_workbook` | bound, punto di congelamento, probabilità condizionate |
| `test_clear_sky_distribution_is_recovered` | `CHOOSE` del cielo asciutto |
| `test_randomized_fields_are_declared_as_snapshots` | i campi randomizzati sono dichiarati |
| `test_extractor_parses_open_ended_mph_ranges` | parsing di `<1`, `1–3`, `73–136` |

Comando:

```powershell
cd sakura-bot
..\.venv\Scripts\python.exe -m pytest tests\unit\test_weather_catalog.py -q
```

## Limiti

- Il workbook è versionato in `docs/xlsx/RPG Weather Dnd5e.xlsx`; i test validano
  il catalogo generato, ma `source.sha256` permette di verificare che il file
  committato sia ancora quello da cui il catalogo è stato estratto.
- I valori `cold_f`/`avg_f`/`hot_f` sono una fotografia e non vanno usati come
  normali climatiche in una validazione scientifica.
- Le frequenze osservate di vento, direzione e fenomeni non sono riproducibili.
- Nessun container, database o client Discord è stato avviato per verificare
  questo mapping: le verifiche sono statiche e sui test unitari.




