# Lot Repéré

Open French public tenders in three trades, **nettoyage et propreté des locaux**, **espaces verts** and **sécurité privée**, refreshed twice a day from free official open data and published as a static site with filters, RSS/Atom, JSON and CSV/ICS downloads (`telechargements/lot-repere-ouverts.csv`, `telechargements/lot-repere-echeances.ics`, rebuilt at every update and served by the site). Paid add-on: a daily e-mail alert per trade, region and keyword (prepaid 3 or 12 months, B2B).

**Site:** https://lot-repere.jalonel.com/ (served at the root of the subdomain; `--site-url` / `SITE_URL` default)

Brand **Jalonel** (https://jalonel.com/), a brand of READ FRANCE SAS (legal operator, named in the legal notice, CGV and invoices). 2026-10-16: moved from https://outils.vread.fr/lot-repere/ (old URLs redirect). IndexNow key file `5be19f56d46ca3d2553bee28ebfa8edd.txt` is written at the site root by the build. Built by copying the pipeline of `VREAD-corp/veille-ao-formation` (MIT, same owner) into this new repo on 2026-10-13; the two repos share no code at runtime. No accounts, no cookies, no LLM at runtime.

## What it does

1. `python -m lotrepere update` fetches:
   - **BOAMP** (DILA) through the Opendatasoft Explore API v2.1: calls for tenders still open, plus everything published in the last 14 days (rectificatifs, cancellations). Server pre-filter = the three niches OR-ed (descriptors, full-text words, CPV prefixes);
   - **TED** search API v3 (no key): French buyers, CPV 90910000, 90911000, 90914000, 90919000, 77310000, 77340000, 77211400, 77211500, 79710000 (hierarchy), calls for competition only.
2. Classifies each notice per niche (`lotrepere/model.py`, `NICHES`, `classify_niches`). A notice belongs to a niche when it is a **services** contract and:
   - a CPV code starts with a niche prefix: nettoyage `90910 90911 90914 90919`; espaces verts `7731 7734 772114 772115`; sécurité `7971`;
   - or a niche BOAMP descriptor is ticked: 239 « Nettoyage de locaux », 116 « Espaces verts », 138 « Gardiennage »; 331 « Surveillance » is weak (counts only next to a niche CPV or keyword) because buyers also use it for network or structure monitoring;
   - or a niche keyword appears in the title or lot names, **only when the notice has no CPV code**.
   A descriptor-only match is dropped when every CPV code of the notice is in the niche's `exclude_cpv` list (street cleaning 9061, refuse 905x, pest control 9092, engineering 71, alarm and CCTV supplies 3512/3232/5032, parking management 6371…). Rules tuned on 2026-10-13 against the real titles of 465 open notices. Each stored notice keeps its BOAMP descriptors, so `store.tenders()` re-applies the current rules without a refetch.
3. Normalises (deadline as written, regions from departments / NUTS, CPV, estimated value, lots), merges into `data/notices.json` and de-duplicates by eForms procedure id (BOAMP + TED copies, rectificatifs). Contact names, e-mails and phones in notices are never copied.
4. `python -m lotrepere build` writes `_site/`: home (all open tenders, filters by keyword, trade, region, deadline), one page per trade, 14 region pages per trade (pages without a local notice are `noindex` and out of the sitemap), `/alertes/`, `/methode/`, legal pages, Atom + RSS, `data/ouverts.json`, sitemap.
5. `python -m lotrepere export` writes the weekly release assets `lot-repere-ouverts.csv` and `lot-repere-echeances.ics`.
6. `python -m lotrepere digest --profile examples/profil-exemple.json` renders a sample digest.

Volumes on 2026-10-13 (open notices): nettoyage 196, espaces verts 155, sécurité privée 89 (436 distinct, a multiservice contract can sit in two trades).

### Feed contract (read by the paid alerts backend)

`data/ouverts.json` = `{generated_at, site, licence, niches: {slug: label}, count, tenders: [...]}`; each tender has `id, title, buyer, url (https), deadline, regions (names), cpv, cpv_libelle, procedure, published, lots, description, status, niches: [slug…]`. Slugs: `nettoyage`, `espaces-verts`, `securite`.

## Paid alerts (prepaid periods)

`sales.config.json` gates the paid tier (`SALES_OPEN`). Products, all sold by the shared octave-pay-gas backend (`VREAD-corp/octave-checkout`, Apps Script, `gas/src/Config.js` is the price authority):

| Product | Price (net, TVA non applicable, art. 293 B du CGI) |
|---|---|
| `lot-repere-3m` | 49 € for 3 months |
| `lot-repere-12m` | 149 € for 12 months (A/B arm a) |
| `lot-repere-12m-b` | 249 € for 12 months (A/B arm b) |

No automatic renewal. Terms: `/cgv-pro/`, version `cgv-pro-lot-repere-2026-10-13`. The order form sends `extra = {niches: [...], regions: [...], keywords: "..."}` (fields marked `data-octave-extra`); the backend reads the public `data/ouverts.json` every morning at about 07:00 Paris and e-mails each subscriber the new matching notices.

**A/B price test** (analysis V4-30 §3): experiment `lot-repere-prix12`, variants a/b, configured in `static/xp-config.js` (`window.OCTAVE_XP`, loaded before `cro.js`), drawn once per tab (sessionStorage), exposure counted on `/alertes/`. `lotrepere/checkout/xp-price.js` switches the 12-month radio to `lot-repere-12m-b` and the shown prices to 249 € in arm b. Outside `/alertes/` the copy only quotes « dès 49 € pour 3 mois », identical in both arms. Force an arm with `?xp_lot-repere-prix12=b`. Both arms stay under the cheapest paid competitor listed in the analysis (marchesonline, from 25 €/month).

`lotrepere/checkout/pay.js`, `devis.js`, `order.js`, `lotrepere/mesure.js` and `lotrepere/cro.js` are verbatim copies of `octave-checkout/gas/web/jalonel/` (the Jalonel tracking copies), `pay.js`, `devis.js` and `order.js` of `octave-checkout/gas/web/`, and `tests/cro.check.mjs` is `gas/web/cro.check.mjs` adapted to the Jalonel host (checked by the tests when that repo sits next to this one). Tracking site id: `lot-repere`. `octave_notrack=1` in the URL disables counting for tests.

Test builds: `SALES_CONFIG=/path/to/sales.json SALES_ALLOW_TEST=1 python -m lotrepere --site-url http://host/ build --out out` accepts a non-Apps-Script endpoint ending in `/exec` and a `pk_test_` key.

## Automation (GitHub Actions)

- `update.yml`: 05:40 and 17:40 UTC, and on push — tests, fetch, commit `data/` if changed, build, deploy Pages. Manual run accepts `since=YYYY-MM-DD` to backfill.
- `weekly-release.yml`: Mondays 06:30 UTC — release `export-YYYY-Www` with the CSV and ICS (never overwritten; archive only since 2026-10-18: the site serves its own downloads from `telechargements/` and no longer links to GitHub).

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python -m lotrepere update            # network
python -m lotrepere build --out _site
```

Python 3.12, standard library only at runtime.

## Sources and licences

- BOAMP — DILA, [Licence Ouverte / Open Licence](https://www.data.gouv.fr/datasets/boamp) (Etalab).
- TED — Publications Office of the EU; reuse under Commission Decision 2011/833/EU ([legal notice](https://ted.europa.eu/en/legal-notice)). TED logos are not used. Not affiliated with the Publications Office or the DILA.
- Code: MIT (see `LICENSE`). Official notices prevail.

## Limits

Not exhaustive: many small contracts (MAPA) are published only on buyer profiles. Classification relies on the codes chosen by buyers.
