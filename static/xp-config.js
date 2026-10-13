/* Lot Repéré: A/B experiments read by cro.js (octave-checkout gas/web/cro.js). Plain script loaded before
 * cro.js so window.OCTAVE_XP exists when cro.js runs (no inline script: the order pages have a strict CSP).
 * lot-repere-prix12: price of the 12-month alert plan, arm a = lot-repere-12m (149 € net), arm b = lot-repere-12m-b (249 € net).
 * Drawn once per tab (sessionStorage), exposure counted on /alertes/ only; ?xp_lot-repere-prix12=b forces an arm. */
window.OCTAVE_XP = [{ id: 'lot-repere-prix12', variants: ['a', 'b'], pages: '/alertes/' }];
