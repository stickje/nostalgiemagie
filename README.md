# Nostalgiemagie

Automatische Instagrampagina met een noodrem via Telegram.

**Elke ochtend** maakt het script de post van vandaag (tekst via Claude, beeld in de huisstijl) en stuurt een voorbeeld naar Telegram.
**Elke avond om 18.00 uur** kijkt het of je op "Overslaan" hebt gedrukt. Zo niet, dan plaatst het de post op Instagram.

## Rubrieken

| Dag | Rubriek | Bron |
|---|---|---|
| ma, di, do, za, zo | Op deze dag | Wikipedia-datumpagina + open foto van het Nationaal Archief (als er een uit hetzelfde jaar is) |
| wo | Vergeten TV | Wikipedia-intro van een Nederlands TV-programma |
| vr | Raad het jaar | Open foto van het Nationaal Archief, carrousel met antwoordslide |

Lukt een rubriek niet, dan valt het script terug op "Op deze dag". Lukt helemaal niets, dan krijg je een melding in Telegram.

## Installatie

1. Maak op GitHub een nieuwe **openbare** repository `nostalgiemagie` en upload alle bestanden (ook de map `.github`).
   Openbaar is nodig omdat Instagram de afbeeldingen van een openbare link ophaalt. Er staan geen geheimen in de code.
2. **Settings → Pages**: kies *Deploy from a branch*, branch `main`, map `/docs`. Noteer het adres, bijvoorbeeld `https://stickje.github.io/nostalgiemagie`.
3. **Settings → Secrets and variables → Actions → Secrets**, voeg toe:
   - `ANTHROPIC_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `IG_ACCESS_TOKEN`
   - `IG_USER_ID`
   - `GH_PAT` (zie stap 4)
4. Maak een **fine-grained personal access token** (GitHub → Settings → Developer settings), alleen voor deze repository, met rechten *Actions: read and write* en *Secrets: read and write*. Deze gebruikt het script om de Instagram-token automatisch te verlengen, en cron-job.org om de runs te starten.
5. **Settings → Secrets and variables → Actions → Variables**, voeg toe:
   - `PAGES_URL` = het adres uit stap 2
   - `DRY_RUN` = `true` (proefmodus; zet op `false` als je live gaat)
6. **cron-job.org**: maak twee jobs, net als bij Daily.
   - URL ochtend: `https://api.github.com/repos/GEBRUIKER/nostalgiemagie/actions/workflows/voorbereiden.yml/dispatches` om 08.00 uur
   - URL avond: `https://api.github.com/repos/GEBRUIKER/nostalgiemagie/actions/workflows/plaatsen.yml/dispatches` om 18.00 uur
   - Methode `POST`, body `{"ref":"main"}`
   - Headers: `Authorization: Bearer <GH_PAT>` en `Accept: application/vnd.github+json`
   - Tijdzone: Europe/Amsterdam (na de verhuizing kun je die gewoon laten staan)

## Testen

Ga naar het tabblad **Actions**, kies *Voorbereiden (ochtend)* en klik op *Run workflow*. Bij "datum" kun je een datum invullen om bijvoorbeeld een vrijdag (Raad het jaar) of woensdag (Vergeten TV) te testen. Daarna kun je *Plaatsen (avond)* handmatig draaien. In proefmodus krijg je alleen een Telegram-bericht dat de post geplaatst zou zijn.

## Week vooruit plannen

Ga naar **Actions → Voorbereiden (ochtend) → Run workflow** en vul bij "dagen" `7` in (bij "datum" eventueel een startdatum, leeg = vandaag).
Je krijgt per dag een voorbeeld in Telegram met een knop **Overslaan**, en aan het eind een overzicht van de week.
Elke avond om 18.00 uur gaat de post van die dag online. Dagen die al gepland zijn worden niet opnieuw gemaakt;
de ochtendrun stuurt dan alleen een herinnering met de knop.

Overslaan kan op drie manieren:
- de knop onder het voorbeeld van die dag (ook dagen vooruit);
- een bericht `overslaan` (de post van vandaag);
- een bericht `overslaan 14-10` (de post van 14 oktober).

Let op: Telegram bewaart berichten aan de bot maar 24 uur. Zolang de ochtend- en avondjobs dagelijks draaien is dat geen probleem.

## Redactie (editor)

In de Nostalgiemagie Redactie kies je per dag een optie en pas je tekst en foto aan:

- **Foto passend maken**: sleep in het voorbeeld om te verplaatsen, scrol of knijp om te zoomen, of gebruik de schuifjes
  (grootte, draaien, links/rechts, omhoog/omlaag) en de knoppen 90° draaien, spiegelen en passend maken.
- **Swipes**: met *Swipe toevoegen* zet je foto's (JPG/PNG) of video's (MP4/WebM, max. 20 MB) achter het voorblad.
  Ze worden vullend 1080 x 1350, met het logo klein in de hoek. Video's worden een MP4 van max. 60 seconden.
  Een post heeft maximaal 10 slides.
- Op vrijdag (Raad het jaar) zijn alle drie de opties Raad het jaar; alleen als er echt geen archieffoto's te vinden
  zijn, vult "Op deze dag" aan.

## Aanpassen

- Toon en regels voor Claude: `writer.py`
- Vormgeving: `dag.html`, `raad.html`, `raad-antwoord.html`, `swipe.html` (swipes met logo)
- Rubriek per weekdag: `config.py`
- Welke TV-categorieën: `sources.py` (rubriek staat nu uit; `tv.html` ontbreekt)
