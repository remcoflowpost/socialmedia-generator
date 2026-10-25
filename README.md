# Flow Social Generator

## Description

Interne tool waarmee The Flow Group on-brand social posts maakt voor meerdere bedrijven en
die in één keer exporteert naar alle platformformaten.

- Een post bestaat uit **lagen** (achtergrond, beeld, logo, tekst, vorm). In fase 2 kan elke
  laag ook AI-gegenereerd zijn met een eigen prompt.
- **Templates zijn merkonafhankelijk.** De brand kit van de afzender (kleuren, fonts, logo)
  kleedt de template aan. Merkkleuren en fonts staan nooit in een template.
- Formaten worden **per formaat opgebouwd** met layoutregels binnen de safe zone, niet geschaald.
- Kwaliteitschecks per formaat: resolutie, safe zones, tekstoverflow, contrast en embargo.
- **Publiceren**: een goedgekeurde, geexporteerde versie inplannen op Facebook-pagina's en
  Instagram-accounts van klanten, met weekplanning, slepen, automatisch versturen en een
  publicatielog. Zie [Publiceren](#publiceren) en `docs/publiceren.md`.

Stand: **fase 1** (fundament en stills) plus **publiceren** (P1-P3). Generatie per laag
(fase 2), video en verdere statussen (fase 3) zijn nog niet gebouwd. LinkedIn volgt na
goedkeuring van de LinkedIn Community Management API.

## Requirements

Productie (één machine of VM):

- Docker Engine 24+ met Docker Compose v2
- Ongeveer 4 GB RAM vrij (Chromium in de render-service)
- Een DNS-naam met publieke TLD en TLS (bijvoorbeeld via een reverse proxy) voor Google OAuth
- Een Google Workspace OAuth-client
- Een Remotion Company License voor gebruik binnen The Flow Group (zie [Remotion](#remotion))

Lokale ontwikkeling:

- Python 3.12 met [uv](https://docs.astral.sh/uv/)
- Node.js 22 met pnpm 10 (`corepack enable`)
- PostgreSQL 16

## Installation

### Met Docker (productie of test op de VM)

```bash
cp .env.example .env          # vul SESSION_SECRET, POSTGRES_PASSWORD, ALLOWLIST en Google-gegevens in
docker compose up -d --build
docker compose exec api python -m app.seed   # templates en drie placeholderbedrijven
```

De web-app draait daarna op `http://<host>:8080` (instelbaar met `WEB_PORT`). Zet er een
reverse proxy met TLS voor en zet `PUBLIC_URL` op dat https-adres.

Opslag staat standaard in een docker-volume. Voor de NAS staat in `docker-compose.yml` een
CIFS-voorbeeld; binnen de containers blijft het pad `/data/storage`.

### Lokaal ontwikkelen

```bash
# Database
createdb flow_social

# API, worker en seed
cd apps/api
uv sync
export SESSION_SECRET=dev AUTH_MODE=dev ALLOWLIST="jij@example.nl=admin"
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000   # terminal 1
uv run python -m app.worker                        # terminal 2

# Frontend en render-service
cd ../..
pnpm install
pnpm --filter @flow/render dev                     # terminal 3, poort 3001
pnpm --filter @flow/web dev                        # terminal 4, http://localhost:5173
```

`AUTH_MODE=dev` geeft een loginscherm zonder Google voor adressen op de allowlist. Dat werkt
alleen met `ENVIRONMENT=development`; de API weigert te starten met dev-login in productie.

## Configuratie

| Variabele | Betekenis |
|---|---|
| `ALLOWLIST` | `email=rol` per gebruiker, gescheiden door komma's. Rollen: `admin`, `editor`. Wie eraf gaat, verliest direct toegang. |
| `SESSION_SECRET` | Sleutel voor de sessiecookie. Verplicht. |
| `PUBLIC_URL` | Basis-URL van de web-app; de OAuth-redirect is `${PUBLIC_URL}/api/auth/callback`. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Workspace OAuth-client. |
| `REMOTION_LICENSE_KEY` | Licentiesleutel van Remotion. Leeg is evaluatie. |
| `RENDER_CONCURRENCY` | Aantal gelijktijdige renders in de render-service (standaard 2). |
| `TOKEN_ENCRYPTION_KEY` | 32 bytes, base64 (`openssl rand -base64 32`). Versleutelt tokens van gekoppelde accounts (AES-256-GCM). Verplicht voor publiceren. Kwijt = alle accounts opnieuw koppelen. |
| `META_APP_ID` / `META_APP_SECRET` | Meta-app (type Business, Facebook Login for Business). Redirect-URI: `${PUBLIC_URL}/api/publishing/connect/meta/callback`. |
| `META_GRAPH_VERSION` | Graph API-versie, standaard `v26.0`. Meta stopt oude versies na ongeveer twee jaar. |
| `ALLOW_SANDBOX_PROVIDER` | `true` zet het Sandbox-netwerk aan (testen zonder Meta). Nooit in productie. |
| `PUBLIC_MEDIA_TTL_SECONDS` | Hoe lang de publieke beeldlink voor Instagram geldig is (standaard 1800). |

Formaten staan in `config/formats.yaml`, inclusief safe zones en de bron per waarde.
Templates staan als YAML in `templates/` en worden met `python -m app.seed` (opnieuw) geladen.

Secrets staan alleen in `.env`, en `.env` staat in `.gitignore`. Open punt uit
`flow-guidelines`: hoe `.env` zich verhoudt tot de Rez-omgeving is nog niet vastgelegd. Deze
tool draait in docker buiten de pipeline, daarom staat `.env` naast `docker-compose.yml`.

## Publiceren

Ontwerp, regels en het exactly-once-mechanisme staan in `docs/publiceren.md`. In het kort:

1. **Accounts koppelen** (Accounts, alleen admins): "Facebook en Instagram koppelen" logt in
   bij Meta. Daarna kies je welke pagina's en Instagram-accounts bij dit bedrijf horen.
   Instagram moet een Business- of Creator-account zijn, gekoppeld aan die Facebook-pagina.
2. **Publicatietijden** per bedrijf instellen, in de tijdzone van dat bedrijf.
3. **Inplannen** (editor, knop "Inplannen"): vereist een opgeslagen versie met een geslaagde
   export, en klantakkoord voor precies die versie. Embargo, kwaliteitsfouten en
   platformregels worden server-side afgedwongen, en vlak voor verzenden opnieuw gecontroleerd.
4. De **worker** verstuurt elke 30 seconden wat aan de beurt is. Mislukt iets, dan staat de
   reden in de Publicatielog, met een veilige knop om het opnieuw te proberen.

**Meta-goedkeuring (buiten de code).** In development mode werkt koppelen alleen voor
mensen met een rol op de Meta-app. Voor klantpagina's is App Review nodig voor
`pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`,
`instagram_content_publish` en `business_management`, plus mogelijk bedrijfsverificatie.
Reken op weken. Meta haalt Instagram-beelden op via een publieke URL, dus `PUBLIC_URL` moet
vanaf internet bereikbaar zijn.

**Bekende beperkingen**

- `instagram/feed-3x4` kan niet via de API: Meta accepteert verhoudingen van 4:5 tot 1.91:1.
- Facebook kent geen idempotency-key. Na een onzekere uitkomst zoekt de worker de post op
  bijschrift in de recente posts van de pagina. Een handmatig geplaatste post met hetzelfde
  bijschrift kan als "al gepubliceerd" worden gezien.
- Paginatokens verlopen niet, maar worden ongeldig als iemand de app-toegang intrekt of zijn
  wachtwoord wijzigt. Het account gaat dan op "opnieuw koppelen" en de planning pauzeert.
- Maximaal 100 API-publicaties per Instagram-account per 24 uur (limiet van Meta).

**Lokaal testen zonder Meta.** Zet `ALLOW_SANDBOX_PROVIDER=true`, voeg bij Accounts een
Sandbox-account toe en plan in zoals gewoonlijk. Met `[sandbox:down]`, `[sandbox:timeout]`,
`[sandbox:ratelimit]`, `[sandbox:reject]` of `[sandbox:auth]` in het bijschrift test je de
foutpaden.

## Merkmateriaal: fonts, achtergronden en elementen

In de Bibliotheek uploaden admins per bedrijf: **Fonts** (WOFF2, WOFF, TTF, OTF),
**Achtergronden** (beelden of SVG) en **Elementen** (transparante PNG of SVG). In de editor
tonen achtergrondlagen de merkachtergronden plus gewone beelden; elementlagen tonen alleen
elementen.

- Fonts worden echt geopend (fontTools). Een font dat insluiten niet toestaat ("restricted
  license embedding") wordt geweigerd. Dit vervangt geen licentiecontrole: ook zonder die vlag
  kan een licentie gebruik op een server verbieden.
- SVG's met actieve inhoud (scripts, event-attributen, `foreignObject`, externe of
  `javascript:`-verwijzingen, DTD's) worden geweigerd. Overige onbekende inhoud (metadata
  van ontwerpprogramma's) wordt verwijderd. SVG's worden geserveerd met een strikte
  Content-Security-Policy.

## Remotion

Preview (browser, `@remotion/player`) en export (server, `renderStill`) gebruiken dezelfde
React-compositie (`packages/compositions`). Zo is de export pixel-gelijk aan wat de editor ziet,
ongeacht de browser van de gebruiker.

**Licentie:** Remotion is gratis voor organisaties tot 3 personen. Daarboven is een Company
License nodig. Deze tool valt onder "Automators" (programmatisch renderen en de Player
embedden), op het moment van schrijven $0,01 per render met een minimum van $100 per maand.
Controleer de actuele voorwaarden op remotion.dev/docs/license. Zet de sleutel in
`REMOTION_LICENSE_KEY`.

Om Remotion los te testen zonder API of database (de dry run van de render-pijplijn):

```bash
cd apps/render
export STORAGE_ROOT=/tmp/flow-smoke
pnpm exec tsx scripts/static-server.ts &      # serveert placeholderbeelden op :3001
pnpm exec tsx scripts/smoke.ts                # rendert alle formaten naar $STORAGE_ROOT/smoke/out
pnpm exec tsx scripts/smoke.ts --small        # met een te kleine foto: resolutiefouten
pnpm exec tsx scripts/smoke.ts --safe-zones   # met zichtbare safe zones
```

Remotion Studio voor de compositie zelf: `pnpm --filter @flow/compositions studio`.

## Providers voor generatie (fase 2)

De generatielaag is nog niet gebouwd. Het ontwerp volgens de spec: een `GenerationProvider`-
interface met een `mock`-adapter als standaard (placeholderbeelden met het prompt erop,
nooit credits) en een `higgsfield`-adapter na akkoord op de integratiekeuze. Templates kunnen
al een `prompt` (PromptSpec) per laag bevatten en assets hebben al een herkomstveld. Zodra
fase 2 er is, beschrijft deze sectie hoe je de mock en een echte provider aanzet.

## Architectuur

```
apps/api            FastAPI, SQLAlchemy 2, Alembic, worker (python -m app.worker)
apps/web            React + Vite, preview met @remotion/player
apps/render         Node-service: Remotion renderStill, sRGB-JPEG, contrastmeting
packages/schema     Gegenereerde TypeScript-types (bron: apps/api/app/schema)
packages/layout     Layout-engine: safe area, anchors, crop met focuspunt, tekst-fit, checks
packages/compositions  React-compositie, gedeeld door preview en export
config/             formats.yaml
templates/          template-definities (YAML)
seed/fonts          OFL-placeholderfonts voor seed-data
```

**Afwijking van de Python-voorkeur.** Frontend, render-service en layout-engine zijn
TypeScript. Remotion en de UI vereisen React. De layout-engine draait in dezelfde Chromium die
ook rendert, omdat tekstmaten alleen daar betrouwbaar zijn. Anders lopen preview, export en
checks uit elkaar. Python blijft eigenaar van data, rechten, jobs en de beslissingen over
kwaliteit (bijvoorbeeld of een post naar "approved" mag).

**Schema's.** De Pydantic-modellen in `apps/api/app/schema` zijn de bron van waarheid. Na een
wijziging:

```bash
cd apps/api && uv run python -m scripts.export_schema && uv run python -m scripts.export_fixtures
cd ../.. && pnpm schema:generate
```

`test_generated_schema_is_up_to_date` faalt als dit vergeten is.

**Jobs.** Exports lopen via de job-tabel in Postgres (`SELECT ... FOR UPDATE SKIP LOCKED`).
Alleen de Python-worker claimt jobs; de render-service is stateless.

**Versies.** Autosave overschrijft de werkkopie. Een nieuwe versie ontstaat bij "Versie
opslaan", bij elke export en (fase 3) bij statuswijzigingen. Een versie bevriest ook de
template en de brand kit, zodat een oude export exact opnieuw te maken is.

**Kleur.** Uploads worden bij inname naar sRGB omgezet (Display P3, Adobe RGB en CMYK). Het
origineel blijft bewaard. Exports krijgen expliciet een sRGB-profiel.

## Tests

```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pytest
pnpm -r test && pnpm -r typecheck
```

De API-integratietests draaien alleen met een aparte testdatabase en weigeren een database
zonder "test" in de naam:

```bash
TEST_DATABASE_URL=postgresql+psycopg://flow:flow@localhost:5432/flow_social_test uv run pytest
```

Tests en seed-data gebruiken alleen placeholders: geen echte klantbeelden, logo's of merkfonts.
Er gaan nooit API-calls naar betaalde providers.
