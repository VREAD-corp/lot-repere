/* Lot Repéré, /alertes/: A/B price test of the 12-month plan (experiment "lot-repere-prix12", arms a and b).
 * cro.js (loaded just before, deferred) draws the arm once per browser tab and sets <html data-xp-lot-repere-prix12>.
 * Arm b: the 12-month radio takes its data-arm-b product id, and every price shown for it (plan cards, radio
 * label, per-month line, pay button) takes its data-b / data-price-b text. Runs before pay.js can read the radios
 * (pay.js loads on the first interaction with the form). The Apps Script catalog stays the price authority:
 * the amount charged is the one of the product id sent. No cro.js (blocked, Do Not Track…): arm a stays. */
(function (d) {
  'use strict';
  var arm = d.documentElement.getAttribute('data-xp-lot-repere-prix12');
  if (arm !== 'b') return;
  Array.prototype.forEach.call(d.querySelectorAll('input[name="product"][data-arm-b]'), function (r) {
    var lbl = r.form && r.form.querySelector('[data-price-for="' + r.value + '"]');
    r.value = r.getAttribute('data-arm-b');
    if (lbl) {
      lbl.setAttribute('data-price-for', r.value);
      lbl.textContent = lbl.getAttribute('data-price-b');
    }
  });
  Array.prototype.forEach.call(d.querySelectorAll('.xp-price[data-b]'), function (el) { el.textContent = el.getAttribute('data-b'); });
  var price = d.getElementById('product-price');
  if (price && price.getAttribute('data-b')) price.textContent = price.getAttribute('data-b');
  var btn = d.getElementById('pay-button');
  if (btn && btn.getAttribute('data-label-b')) btn.textContent = btn.getAttribute('data-label-b');
})(document);
