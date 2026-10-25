# Publiceren en inplannen (fase P)

Plan voor het toevoegen van automatisch publiceren aan de Flow Social Generator. Geschreven
vóór de implementatie. De publicatielogica is overgenomen uit Queuebird (exactly-once
publisher, queue-tijden, swap bij slepen, publicatielog) en aangepast aan het model van de
generator: meerdere bedrijven, teamrollen, versies, embargo en klantgoedkeuring.

## Keuzes (met Remco afgestemd, 25 oktober 2026)

| Vraag | Keuze |
|---|---|
| Waar woont publiceren | In de generator (Python-API, React-web). Queuebird is de bron voor logica en tests, de Next.js-app vervalt. |
| Automatische posts | Template + brand kit (bestaat grotendeels), en AI-generatie per laag (fase 2 van de generator, zie onderaan) |
| Accounts | Pagina's van klanten |
| Volgorde | Facebook + Instagram eerst (één Meta-app, één review), LinkedIn daarna |

## Wat buiten de code om moet gebeuren (kritiek pad)

1. **Meta-app aanmaken** (developers.facebook.com, type *Business*), product *Facebook Login for
   Business*, en een publieke privacyverklaring. In development mode werkt de koppeling alleen
   voor mensen met een rol op de app: genoeg om te bouwen en de screencast op te nemen.
2. **App Review** voor `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
   `instagram_basic`, `instagram_content_publish` en `business_management`. Reken op
   meerdere weken, inclusief mogelijke afwijzingen. Dien in zodra de flow in deze branch
   werkt.
3. Mogelijk **bedrijfsverificatie** (Business Verification / Access Verification) omdat The
   Flow Group namens andere bedrijven publiceert.
4. **LinkedIn**: Community Management API aanvragen (Development tier, daarna Standard tier).
   Pas na goedkeuring bouwen we de LinkedIn-adapter. De interface staat er al klaar voor.
5. **Klant-Instagram** moet een Business- of Creator-account zijn, gekoppeld aan de
   Facebook-pagina van die klant. De persoon die koppelt moet de pagina mogen beheren.

## Platformregels die de code afdwingt

| Platform | Formaten uit `formats.yaml` | Bijschrift | Beeld |
|---|---|---|---|
| Instagram feed | `instagram/feed-square`, `instagram/feed-portrait` | max. 2200 tekens, max. 30 hashtags | JPEG, ≤ 8 MB, verhouding 4:5 t/m 1.91:1 |
| Instagram story | `instagram/story` | geen bijschrift | JPEG, ≤ 8 MB |
| Facebook-pagina | `facebook/feed-landscape`, `facebook/feed-square` | max. 63.206 tekens | JPEG of PNG |

- **`instagram/feed-3x4` (1080×1440) is niet via de API te publiceren.** Meta weigert
  verhoudingen smaller dan 4:5 (fout 2207009). Exporteren blijft mogelijk, inplannen niet.
- Instagram haalt het beeld zelf op via een **publieke URL**. De API geeft per publicatie een
  ondertekende link uit die 30 minuten geldig is en alleen dat ene bestand serveert. `PUBLIC_URL`
  moet daarvoor vanaf internet bereikbaar zijn.
- Maximaal 100 API-publicaties per Instagram-account per 24 uur. De planner weigert meer.

## Bedrijfsregels voor een publicatie (server-side)

Een publicatie mag alleen worden ingepland als:

1. de post een **opgeslagen versie** heeft met een **geslaagde export** voor het gekozen formaat
   (we publiceren nooit een werkkopie, alleen een bevroren versie);
2. die export **geen kwaliteitsfout** (`severity = error`) heeft;
3. de post **door de klant is goedgekeurd** (`client_approved`), want we publiceren op klantpagina's;
4. het tijdstip **na het embargo** ligt (`embargo_until`);
5. het account **actief** is en bij **hetzelfde bedrijf** hoort als de post;
6. het formaat bij het platform past (tabel hierboven) en het bijschrift binnen de limiet valt;
7. het tijdstip in de toekomst ligt en hooguit een jaar vooruit.

Deze regels worden opnieuw gecontroleerd vlak voor het verzenden. Is er intussen iets
veranderd (goedkeuring ingetrokken, embargo verschoven, account gepauzeerd), dan wordt er
niet gepubliceerd. De reden komt in de publicatielog.

## Datamodel (nieuwe tabellen)

Alle tijden zijn `timestamptz`. Lokale planning gebruikt de tijdzone van het bedrijf (nieuwe
kolom `companies.timezone`, standaard `Europe/Amsterdam`).

### `social_accounts`
Gekoppeld account (Facebook-pagina of Instagram-account) van een bedrijf.
`id`, `company_id`, `provider` (`facebook_page`, `instagram`, `sandbox`), `external_id`
(page-id / ig-user-id), `name`, `handle`, `token_enc` (AES-256-GCM, AAD = account-id),
`token_expires_at`, `status` (`active`, `reauth_required`, `disconnected`), `status_reason`,
`connected_by`, `last_checked_at`, tijdstempels. Uniek: (`company_id`, `provider`,
`external_id`) zolang niet ontkoppeld.

### `publish_slots`
Terugkerende publicatietijden per bedrijf: `company_id`, `weekday` 1–7, `local_time`.
Uniek per (bedrijf, dag, tijd).

### `publications`
Eén beeld van één postversie naar één account op één moment. Dit is tegelijk de job.
`id`, `company_id`, `post_id`, `post_version_id`, `format_key`, `media_key` (bestand uit de
export), `social_account_id`, `caption`, `status` (`scheduled`, `publishing`, `published`,
`failed`, `cancelled`), `scheduled_at`, `schedule_tz`, `idempotency_key` (vast),
`attempt_count`, `retry_base`, `first_attempt_at`, `next_attempt_at`, `lease_expires_at`,
`provider_container_id` (Instagram), `provider_post_id`, `provider_url`, `failure_code`,
`failure_message`, `failure_retryable`, `version`, `created_by`, tijdstempels.

- **Exclusieconstraint** (deferrable): hooguit één `scheduled`/`publishing` publicatie per
  account per moment. Verschuiven geeft het oude slot in dezelfde transactie vrij, en een
  swap gebeurt in één transactie.

### `publish_attempts`
Onveranderlijke log van elke poging (trigger weigert wijzigen na afronden en weigert
verwijderen). Velden zoals in Queuebird, plus `container_id`.

## Exactly-once bij Meta

Meta kent geen idempotency-key. Daarom:

- **Instagram**: het container-id wordt opgeslagen *vóór* `media_publish`. Bij een onzekere
  uitkomst vraagt de worker de container-status op. `PUBLISHED` betekent dat de post al live
  staat: we zoeken het media-id op en zenden niets opnieuw. `FINISHED` betekent dat dezelfde
  container opnieuw gepubliceerd kan worden. Bij `EXPIRED` of `ERROR` maken we een nieuwe
  container.
- **Facebook**: bij een onzekere uitkomst zoeken we in de recente posts van de pagina naar
  hetzelfde bijschrift na het eerste verzendmoment. Gevonden betekent gepubliceerd. Niet
  gevonden betekent opnieuw verzenden. Het restrisico (identiek bijschrift handmatig
  geplaatst) staat in de README.
- Claimen met `FOR UPDATE SKIP LOCKED` plus een lease. Elke providercall wordt voorafgegaan
  door een `in_progress`-poging. Afronden is beveiligd met status en pogingnummer.
- Automatische retries (1, 5 en 15 min, `Retry-After` gaat voor), daarna handmatig. Een
  handmatige retry na een onzekere uitkomst vraagt een bevestiging.
- Meer dan een uur te laat: niet alsnog publiceren (`missed_window`).

## Foutclassificatie Meta

| Graph-fout | Betekenis | Gedrag |
|---|---|---|
| code 190 (OAuthException), 102, 10, 200-299 | token ongeldig of rechten ingetrokken | account `reauth_required`, publicatie mislukt |
| code 4, 17, 32, 613, 80001-80009 | rate limit | retry met backoff |
| `is_transient: true`, HTTP 5xx | tijdelijk | retry; onzeker bij timeouts na verzenden |
| code 9007 / 2207027 | media nog niet klaar | opnieuw controleren |
| code 100, 2207009, 2207004, 368 | ongeldige inhoud of geblokkeerd | mislukt, niet automatisch opnieuw |

## Componenten

| Laag | Bestand |
|---|---|
| Domeinregels (puur, getest) | `app/publishing/rules.py`, `app/publishing/slots.py`, `app/publishing/retry.py` |
| Opslag + transacties | `app/publishing/service.py` |
| Providers | `app/publishing/providers/{base,meta,sandbox}.py` |
| Worker | `app/publishing/worker.py`, aangeroepen vanuit `app/worker.py` (elke 30 s) |
| API | `app/api/publishing.py` |
| Web | `apps/web/src/pages/PlanningPage.tsx`, `AccountsPage`, `PublicationLogPage`, `editor/ScheduleDialog.tsx` |

## Fases

| Fase | Inhoud | Status |
|---|---|---|
| P1 | Backend: model, migratie, regels, sandbox- en Meta-adapter, publisher, API, tests | klaar |
| P2 | Web: accounts koppelen, inplannen vanuit export, weekplanning met slepen, publicatielog | klaar |
| P3 | Merkmateriaal: achtergronden en elementen als soort, fontvalidatie, SVG-opschoning | klaar (zonder brand-kit-wijziging: de bibliotheek is al per bedrijf) |
| P4 | LinkedIn-adapter (na API-goedkeuring) | wacht op LinkedIn |
| P5 | AI-generatie per laag: dit is fase 2 van de generator zelf (`GenerationProvider`, mock en daarna Higgsfield na akkoord). Niet in deze branch, om dubbel werk met die planning te voorkomen. | gepland |

## Open punten (niet zelf ingevuld)

- **`.env` vs. Rez** (flow-guidelines): de nieuwe secrets (`TOKEN_ENCRYPTION_KEY`,
  `META_APP_ID`, `META_APP_SECRET`) staan net als de bestaande in `.env`. Dezelfde open vraag
  geldt hier.
- **Wie mag publiceren**: voorstel is dat editors kunnen inplannen en admins accounts
  koppelen en ontkoppelen. Dit is nog te bevestigen.
- **Publieke bereikbaarheid**: Instagram moet de afbeelding kunnen downloaden. Als de VM
  alleen intern bereikbaar is, is een publiek pad nodig, bijvoorbeeld een aparte route via de
  reverse proxy.

## Gevonden tijdens de bouw

- `client_approved` bestond in het model, maar niets in de API zette het. Er is nu een
  akkoord per versie (`client_approved_version`).
- `PUT /api/posts/{id}` verwacht snake_case (`embargo_until`), de rest van de API camelCase.
  Onbekende velden worden stil genegeerd. Advies: één conventie en `extra="forbid"`.
- De SVG-check bij upload liet `onload`, `foreignObject`, XXE en externe verwijzingen door;
  fonts werden alleen op extensie gecontroleerd; `kind` werd niet gevalideerd. Alle drie
  opgelost in P3.
- De bestaande jobtabel heeft geen lease: een job die op `running` blijft hangen na een
  crash van de worker, wordt nooit opnieuw opgepakt. Publicaties hebben wel een lease; voor
  exports is dit nog open.
