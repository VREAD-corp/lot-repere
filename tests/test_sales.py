"""Sales gate of the paid alerts (sales.config.json SALES_OPEN), the subscription page and the A/B price test."""

import html as htmlmod
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lotrepere import boamp, sales, store
from lotrepere.geo import REGION_SLUGS
from lotrepere.model import NICHE_SLUGS
from lotrepere.site import Site

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)
SITE = "https://example.org/lot-repere/"
CRO_TAG = re.compile(r'<script src="[^"]*/cro\.js" [^>]*></script>')
BUY_MARKERS = ["js.stripe.com", "checkout-config", "octave-pay", "pk_live_", "pk_test_", "commande.html"]
TEST_OPEN = dict(SALES_OPEN=True, endpoint="https://octave-test.invalid/exec", publishableKey="pk_test_fake123")
# Canonical scripts: local octave-checkout checkout (absent in CI; OCTAVE_CHECKOUT overrides the location).
GAS_WEB = Path(os.environ.get("OCTAVE_CHECKOUT") or ROOT.parent / "octave-checkout") / "gas" / "web"


def cfg(tmp_path, **over):
    c = json.loads((ROOT / "sales.config.json").read_text())
    c.update(over)
    f = tmp_path / f"sales-{len(list(tmp_path.iterdir()))}.json"
    f.write_text(json.dumps(c))
    return f


def build(tmp_path, s):
    db = {}
    store.merge(db, boamp.normalise_all(json.loads((FIX / "boamp_records.json").read_text())["results"], today="2026-10-13"))
    out = tmp_path / f"site-{s.open}-{len(list(tmp_path.iterdir()))}"
    Site(out, SITE, NOW, sales=s).build(store.tenders(db), {"updated_at": "2026-10-13T04:20:00+00:00"})
    return out


def opened(tmp_path, monkeypatch, **over):
    monkeypatch.setenv("SALES_ALLOW_TEST", "1")
    return build(tmp_path, sales.load(cfg(tmp_path, **{**TEST_OPEN, **over})))


def jsonld(html):
    out = []
    for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        d = json.loads(b)
        out.extend(d if isinstance(d, list) else [d])
    return out


def test_committed_config_is_coherent():
    s = sales.load(ROOT / "sales.config.json")
    assert s.products == {"lot-repere-3m": 4900, "lot-repere-12m": 14900, "lot-repere-12m-b": 24900}
    assert s.vat == "franchise293B" and sales.TERMS_VERSION == "cgv-pro-lot-repere-2026-10-13"
    assert sales.PLAN_ARMS == {"a": "lot-repere-12m", "b": "lot-repere-12m-b"} and sales.PRICE_XP == "lot-repere-prix12"
    # the paid alert stays the cheapest paid offer of the analysis (V4-30 §3: marchesonline from 25 €/month)
    assert max(s.products.values()) < 300_00
    assert s.endpoint.startswith("https://script.google.com/macros/s/") and s.publishable_key.startswith("pk_live_")


def test_open_needs_apps_script_endpoint_and_live_key(tmp_path, monkeypatch):
    monkeypatch.delenv("SALES_ALLOW_TEST", raising=False)
    with pytest.raises(ValueError):
        sales.load(cfg(tmp_path, SALES_OPEN=True, endpoint="", publishableKey=""))
    with pytest.raises(ValueError):
        sales.load(cfg(tmp_path, SALES_OPEN=True, endpoint="https://evil.example/exec", publishableKey="pk_live_x"))
    with pytest.raises(ValueError):
        sales.load(cfg(tmp_path, products={"lot-repere-3m": 4900, "lot-repere-12m": 14900}))
    assert sales.load(cfg(tmp_path, SALES_OPEN=True, endpoint="https://script.google.com/macros/s/AKfycbTESTTESTTESTTESTTEST/exec", publishableKey="pk_live_x")).open


def test_closed_build_has_no_buy_ui(tmp_path):
    out = build(tmp_path, sales.load(cfg(tmp_path, SALES_OPEN=False)))
    assert not (out / "checkout").exists() and not (out / "cgv-pro").exists() and not (out / "alertes" / "commande.html").exists()
    for f in out.rglob("*"):
        if f.suffix in (".html", ".js", ".xml", ".txt", ".json") and f.is_file() and f.name not in ("mesure.js", "cro.js", "cro-goals.js"):
            body = CRO_TAG.sub("", f.read_text(encoding="utf-8"))
            for m in BUY_MARKERS:
                assert m not in body, f"{f}: {m}"
    page = (out / "alertes" / "index.html").read_text()
    assert "aucun paiement n'est possible" in page
    assert not any(i.get("@type") == "Product" for i in jsonld(page))


def test_open_build_order_form(tmp_path, monkeypatch):
    out = opened(tmp_path, monkeypatch)
    page = (out / "alertes" / "index.html").read_text()
    assert "Content-Security-Policy" in page and "https://octave-test.invalid" in page
    form = page[page.index('<form id="octave-pay"'):page.index("</form>", page.index('<form id="octave-pay"'))]
    # the extra fields read by octave-checkout (Alerts.js): niches, regions, keywords; no CPV family any more
    for slug in NICHE_SLUGS:
        assert f'name="niches" value="{slug}" data-octave-extra' in form
    assert 'name="niches" value="nettoyage" data-octave-extra checked' in form
    for slug in REGION_SLUGS:
        assert f'name="regions" value="{slug}" data-octave-extra>' in form
    assert form.count('name="regions"') == 14 and 'name="keywords" data-octave-extra' in form and 'name="cpv"' not in form
    # plans: 12 months (arm a by default, arm b id carried for xp-price.js) and 3 months
    assert 'name="product" value="lot-repere-12m" data-arm-a="lot-repere-12m" data-arm-b="lot-repere-12m-b" checked' in form
    assert 'name="product" value="lot-repere-3m"' in form
    assert "149,00 € net (TVA non applicable, art. 293 B du CGI)" in form and 'data-price-b="249,00 € net (TVA non applicable, art. 293 B du CGI)"' in form
    assert "49,00 € net" in form and "sans renouvellement automatique" in form
    for n in ("email", "company", "siren", "addressLine1", "postalCode", "city", "terms"):
        assert f'name="{n}"' in form, n
    assert 'id="pay-button" class="pay-button" data-cta data-label-b="Payer 249 € et activer mes alertes" disabled>Payer 149 € et activer mes alertes</button>' in form
    # scripts: config, lazy Stripe loader, criteria checks, then the deferred A/B price switch
    assert '<script src="https://js.stripe.com/v3/">' not in page
    assert '<script src="/lot-repere/checkout/stripe-lazy.js" data-pay="/lot-repere/checkout/pay.js"></script>' in page
    assert page.index("checkout/alerts-form.js") < page.index('checkout/xp-price.js" defer')
    conf = (out / "checkout" / "checkout-config.js").read_text()
    assert '"offers": {"lot-repere-3m": {"amount": 4900}, "lot-repere-12m": {"amount": 14900}, "lot-repere-12m-b": {"amount": 24900}}' in conf
    assert '"termsVersion": "cgv-pro-lot-repere-2026-10-13"' in conf and '"product": "lot-repere-12m"' in conf
    assert '"termsUrl": "/lot-repere/cgv-pro/"' in conf and '"orderPage": "commande.html"' in conf
    ids = Counter(re.findall(r'\sid="([^"]+)"', page))
    assert [i for i, n in ids.items() if n > 1] == []
    ret = (out / "alertes" / "commande.html").read_text()
    assert 'id="order-status"' in ret and '<meta name="robots" content="noindex">' in ret
    sitemap = (out / "sitemap.xml").read_text()
    assert SITE + "alertes/" in sitemap and "cgv-pro" not in sitemap and "commande" not in sitemap


def test_price_outside_alerts_never_shows_the_tested_12_month_price(tmp_path, monkeypatch):
    out = opened(tmp_path, monkeypatch)
    for f in out.rglob("*.html"):
        rel = f.relative_to(out).as_posix()
        if rel.startswith(("alertes/", "cgv-pro/", "confidentialite/")):
            continue
        body = f.read_text()
        assert "149" not in body.replace("1490", "") or "149 €" not in body, rel
        assert "149 €" not in body and "249 €" not in body, rel
    index = (out / "index.html").read_text()
    assert "dès 49 € pour 3 mois" in index


def test_ab_price_switch_markup(tmp_path, monkeypatch):
    out = opened(tmp_path, monkeypatch)
    page = (out / "alertes" / "index.html").read_text()
    xp = (out / "static" / "xp-config.js").read_text()
    assert "id: 'lot-repere-prix12', variants: ['a', 'b'], pages: '/alertes/'" in xp
    head = page.split("</head>")[0]
    assert head.index("static/xp-config.js") < head.index("/cro.js")
    assert 'class="xp-price" data-a="149 €" data-b="249 €">149 €</span>' in page
    assert 'class="xp-price" data-a="12,42 €" data-b="20,75 €">12,42 €</span>' in page
    js = (out / "checkout" / "xp-price.js").read_text()
    assert "data-xp-lot-repere-prix12" in js and "data-arm-b" in js
    # terms state both prices of the test, privacy explains it
    cgv = (out / "cgv-pro" / "index.html").read_text()
    assert "149,00 € net" in cgv and "249,00 € net" in cgv and "49,00 € net" in cgv
    privacy = (out / "confidentialite" / "index.html").read_text()
    assert "Test A/B en cours" in privacy and "149 €" in privacy and "249 €" in privacy


@pytest.mark.skipif(not __import__("shutil").which("node"), reason="node not installed")
def test_xp_price_js_switches_arm_b(tmp_path, monkeypatch):
    """Runs checkout/xp-price.js on a tiny DOM stub: arm b switches the radio value and the visible prices."""
    import subprocess
    script = r"""
const fs = require('fs');
const code = fs.readFileSync(process.argv[2], 'utf8');
function el(attrs, text) { return { attrs, textContent: text, getAttribute(k) { return this.attrs[k] ?? null; }, setAttribute(k, v) { this.attrs[k] = v; } }; }
for (const arm of ['a', 'b']) {
  const lbl = el({ 'data-price-for': 'lot-repere-12m', 'data-price-b': 'B' }, 'A');
  const form = { querySelector: (s) => (s === '[data-price-for="lot-repere-12m"]' ? lbl : null) };
  const radio = Object.assign(el({ 'data-arm-b': 'lot-repere-12m-b' }), { value: 'lot-repere-12m', form });
  const span = el({ 'data-b': '249' }, '149');
  const btn = el({ 'data-label-b': 'Payer 249' }, 'Payer 149');
  const document = {
    documentElement: el({ 'data-xp-lot-repere-prix12': arm }),
    querySelectorAll: (s) => (s.startsWith('input') ? [radio] : [span]),
    getElementById: (id) => (id === 'pay-button' ? btn : null),
  };
  new Function('document', code)(document);
  console.log(arm, radio.value, lbl.textContent, lbl.getAttribute('data-price-for'), span.textContent, btn.textContent);
}
"""
    f = tmp_path / "t.cjs"
    f.write_text(script)
    r = subprocess.run(["node", str(f), str(ROOT / "lotrepere" / "checkout" / "xp-price.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["a lot-repere-12m A lot-repere-12m 149 Payer 149", "b lot-repere-12m-b B lot-repere-12m-b 249 Payer 249"]


def test_open_build_terms_and_privacy(tmp_path, monkeypatch):
    out = opened(tmp_path, monkeypatch)
    cgv = (out / "cgv-pro" / "index.html").read_text()
    assert "PAS UN CONSEIL JURIDIQUE" in cgv and '<meta name="robots" content="noindex">' in cgv
    for needle in ["version du 13 octobre 2026", "cgv-pro-lot-repere-2026-10-13", "au capital de 1 000 €", "SIREN 988 741 773",
                   "TVA non applicable, art. 293 B du CGI", "Lot Repéré", "nettoyage de locaux", "sécurité privée",
                   "période ferme et prépayée de 3 mois ou de 12 mois", "ni renouvelé ni prélevé automatiquement",
                   "arrêter les alertes à tout moment", "n'est pas exhaustive", "ne s'applique pas", "limitée au prix payé",
                   "40 €", "CNIL", "tribunaux de Paris"]:
        assert needle in cgv, needle
    assert "formation" not in cgv.lower().replace("information", "")
    privacy = (out / "confidentialite" / "index.html").read_text()
    assert "Abonnement aux alertes e-mail" in privacy and "métiers, régions, mots-clés" in privacy
    assert 'href="/lot-repere/cgv-pro/">CGV</a>' in (out / "index.html").read_text()


def test_open_build_jsonld(tmp_path, monkeypatch):
    out = opened(tmp_path, monkeypatch)
    page = (out / "alertes" / "index.html").read_text()
    items = jsonld(page)
    product = next(i for i in items if i.get("@type") == "Product")
    assert product["brand"] == {"@type": "Brand", "name": "Lot Repéré"} and product["sku"] == "lot-repere-alertes"
    offers = {o["name"]: o for o in product["offers"]}
    assert offers["3 mois"]["@type"] == "Offer" and offers["3 mois"]["price"] == "49.00"
    agg = offers["12 mois"]
    assert agg["@type"] == "AggregateOffer" and (agg["lowPrice"], agg["highPrice"], agg["offerCount"]) == ("149.00", "249.00", 2)
    faq = next(i for i in items if i.get("@type") == "FAQPage")
    assert len(faq["mainEntity"]) == page.count('class="faq-item"') == 7
    assert all(q["acceptedAnswer"]["text"] and "<" not in q["acceptedAnswer"]["text"] for q in faq["mainEntity"])
    assert "aggregateRating" not in page and '"review' not in page
    title = htmlmod.unescape(re.search(r"<title>(.*?)</title>", page).group(1))
    desc = htmlmod.unescape(re.search(r'<meta name="description" content="([^"]*)">', page).group(1))
    assert len(desc) <= 170 and "49 € net" in desc and "149" not in desc and "Lot Repéré" in title


def test_no_ht_ttc_on_our_prices(tmp_path, monkeypatch):
    out = opened(tmp_path, monkeypatch)
    for f in ("alertes/index.html", "cgv-pro/index.html", "index.html"):
        body = (out / f).read_text().replace("€ HT (estimation)", "")
        assert "TTC" not in body and "€ HT" not in body, f


def test_quotes_flag_off_when_committed(tmp_path, monkeypatch):
    assert json.loads((ROOT / "sales.config.json").read_text())["quotesEnabled"] is False
    out = opened(tmp_path, monkeypatch, quotesEnabled=False)
    page = (out / "alertes" / "index.html").read_text()
    assert "octave-devis" not in page and "devis.js" not in page


def test_quotes_on_build_has_the_same_extra_fields(tmp_path, monkeypatch):
    out = opened(tmp_path, monkeypatch, quotesEnabled=True)
    page = (out / "alertes" / "index.html").read_text()
    card = page[page.index('<form id="octave-pay"'):page.index("</form>", page.index('<form id="octave-pay"'))]
    quote = page[page.index('<form id="octave-devis"'):page.index("</form>", page.index('<form id="octave-devis"'))]
    extra = r'<input [^>]*data-octave-extra[^>]*>'
    strip = lambda tags: [re.sub(r'\s(?:id|aria-describedby)="[^"]*"', "", t) for t in tags]
    assert strip(re.findall(extra, quote)) == strip(re.findall(extra, card))
    ids = Counter(re.findall(r'\sid="([^"]+)"', page))
    assert [i for i, n in ids.items() if n > 1] == []


@pytest.mark.skipif(not GAS_WEB.is_dir(), reason="octave-checkout checkout not next to this repo")
def test_vendored_checkout_scripts_match_octave_checkout():
    for f in ("pay.js", "devis.js", "order.js"):
        assert (ROOT / "lotrepere" / "checkout" / f).read_bytes() == (GAS_WEB / f).read_bytes(), f


def test_home_first_screen_is_the_tool(tmp_path, monkeypatch):
    # JALONEL-HUB-02: H1, one sentence and the alerts link with its starting price, then the filters and the list;
    # counts per trade, the full price note and the e-mail preview come after the list.
    index = (opened(tmp_path, monkeypatch) / "index.html").read_text()
    hero, rest = index.split('<section aria-labelledby="filtres-titre"', 1)
    words = lambda h: [w for w in re.sub(r"<[^>]+>", " ", h).split() if re.search(r"\w", w)]
    top = hero.split("<h1>", 1)[1]
    assert len(words(top.split('<p class="hero-alert"')[0])) <= 30 and len(words(top)) <= 42
    assert 'alertes/" data-cta>' in top and "pour 3 mois" in top
    after = rest.split('id="liste-titre"', 1)[1]
    assert 'id="apercu-alertes"' in after and "niche-tiles" in after and "CGV, art. 9" in after
