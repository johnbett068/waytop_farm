(function () {
  'use strict';
  const page = document.querySelector('[data-checkout-page]');
  const confirmation = document.querySelector('[data-checkout-confirmation]');
  const storageKey = 'waytop-commerce-v1';
  const checkoutKey = 'waytop-checkout-preview-v1';

  function money(value) { return 'KES ' + Math.round(value).toLocaleString('en-KE'); }
  function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, function (char) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]; }); }
  function catalog() {
    const node = document.getElementById('commerce-catalog-data');
    try { return JSON.parse(node ? node.textContent : '[]'); } catch (error) { return []; }
  }
  function savedCart() {
    try {
      const cart = JSON.parse(localStorage.getItem(storageKey) || '{}').cart || {};
      if (page && page.dataset.stateMode === 'success' && Object.keys(cart).length === 0) return { 'anna-f1-tomato': { quantity: 2 }, 'hass-avocado': { quantity: 4 } };
      return cart;
    } catch (error) { return {}; }
  }
  function entries() {
    const products = new Map(catalog().map(function (item) { return [item.slug, item]; }));
    return Object.keys(savedCart()).map(function (slug) {
      const product = products.get(slug); const item = savedCart()[slug] || {};
      return product ? { product: product, quantity: Math.min(99, Math.max(1, parseInt(item.quantity, 10) || 1)) } : null;
    }).filter(Boolean);
  }

  if (confirmation) {
    try {
      const preview = JSON.parse(sessionStorage.getItem(checkoutKey) || '{}');
      if (preview.fulfillment === 'pickup') {
        confirmation.querySelector('[data-confirmation-estimate]').textContent = 'Pickup timing confirmed after availability review';
        confirmation.querySelector('[data-confirmation-fulfillment]').textContent = 'Farm Pickup';
      }
      if (preview.payment === 'cash_pickup') confirmation.querySelector('[data-confirmation-payment]').textContent = 'Due on pickup — mock only';
    } catch (error) { /* Static fallback remains valid. */ }
    const title = confirmation.querySelector('h1'); if (title) title.focus();
    return;
  }
  if (!page) return;

  const form = page.querySelector('[data-checkout-form]');
  const layout = page.querySelector('[data-checkout-layout]');
  const loading = page.querySelector('[data-checkout-loading]');
  const empty = page.querySelector('[data-checkout-empty]');
  const errorState = page.querySelector('[data-checkout-error]');
  const permission = page.querySelector('[data-checkout-permission]');
  const panels = Array.from(page.querySelectorAll('[data-checkout-step]'));
  const indicators = Array.from(page.querySelectorAll('[data-step-indicator]'));
  const next = page.querySelector('[data-checkout-next]');
  const back = page.querySelector('[data-checkout-back]');
  const submit = page.querySelector('[data-checkout-submit]');
  const validationSummary = page.querySelector('[data-validation-summary]');
  let step = 1;
  const cartEntries = entries();

  function subtotal() { return cartEntries.reduce(function (sum, entry) { return sum + entry.product.price * entry.quantity; }, 0); }
  function fulfillment() { return (form.elements.fulfillment || {}).value || 'delivery'; }
  function payment() { return (form.elements.payment || {}).value || 'mpesa'; }
  function deliveryFee() { return fulfillment() === 'delivery' ? 350 : 0; }
  function labelForFulfillment() { return fulfillment() === 'delivery' ? 'Home Delivery · ' + money(350) : 'Farm Pickup · Free'; }
  function labelForPayment() { return payment() === 'cash_pickup' ? 'Cash on Pickup' : 'M-Pesa'; }

  function renderSummary() {
    page.querySelector('[data-checkout-summary-items]').innerHTML = cartEntries.map(function (entry) {
      return '<article class="checkout-summary-item"><img src="' + escapeHtml(entry.product.image_url) + '" alt=""><div><h3>' + escapeHtml(entry.product.name) + '</h3><p>' + entry.quantity + ' × ' + escapeHtml(entry.product.unit) + '</p></div><strong>' + money(entry.product.price * entry.quantity) + '</strong></article>';
    }).join('');
    const total = subtotal() + deliveryFee();
    page.querySelector('[data-checkout-subtotal]').textContent = money(subtotal());
    page.querySelector('[data-checkout-delivery]').textContent = labelForFulfillment();
    page.querySelector('[data-checkout-payment]').textContent = labelForPayment();
    page.querySelector('[data-checkout-total]').textContent = money(total);
    page.querySelector('[data-summary-toggle-total]').textContent = money(total);
    const notes = form.elements.notes.value.trim(); const noteBox = page.querySelector('[data-summary-notes]');
    noteBox.hidden = !notes; noteBox.querySelector('span').textContent = notes;
  }

  function configureFulfillment() {
    const delivery = fulfillment() === 'delivery';
    const address = page.querySelector('[data-delivery-address]'); address.hidden = !delivery;
    address.querySelectorAll('input, select, textarea').forEach(function (field) { field.required = delivery; field.disabled = !delivery; });
    const cash = form.querySelector('[data-payment="cash_pickup"]'); const cashOption = page.querySelector('[data-cash-option]');
    cash.disabled = delivery; cashOption.classList.toggle('is-disabled', delivery);
    if (delivery && cash.checked) form.querySelector('[data-payment="mpesa"]').checked = true;
    renderSummary();
  }

  function fieldMessage(field) {
    if (field.name === 'phone' && field.value && !/^\+254\s?\d{3}\s?\d{3}\s?\d{3}$/.test(field.value.trim())) return 'Enter a Kenyan phone number such as +254 724 853 914.';
    if (field.validity.valueMissing) return ({ full_name: 'Enter the customer’s full name.', phone: 'Enter a phone number for fulfillment updates.', email: 'Enter an email address.', county: 'Select the delivery county.', town: 'Enter the delivery town or area.', address: 'Enter a delivery address with a useful landmark.' })[field.name] || 'Complete this field.';
    if (field.validity.typeMismatch && field.name === 'email') return 'Enter an email address in the format name@example.com.';
    if (field.validity.tooShort) return 'Enter at least two characters.';
    return '';
  }

  function validateStep() {
    const panel = panels[step - 1]; const fields = Array.from(panel.querySelectorAll('input, select, textarea')).filter(function (field) { return !field.disabled && field.type !== 'radio' && field.name !== 'confirm_review'; });
    const errors = [];
    fields.forEach(function (field) {
      const message = fieldMessage(field); field.setAttribute('aria-invalid', String(Boolean(message)));
      const error = field.closest('.checkout-field') && field.closest('.checkout-field').querySelector('[data-field-error]');
      if (error) { error.textContent = message; if (!error.id) error.id = 'error-' + field.name; field.setAttribute('aria-describedby', error.id); }
      if (message) errors.push({ field: field, message: message });
    });
    if (step === 4 && !form.elements.confirm_review.checked) {
      const message = 'Confirm that you reviewed the request before submitting.'; page.querySelector('[data-consent-error]').textContent = message;
      form.elements.confirm_review.setAttribute('aria-invalid', 'true'); errors.push({ field: form.elements.confirm_review, message: message });
    }
    validationSummary.hidden = errors.length === 0;
    validationSummary.querySelector('ul').innerHTML = errors.map(function (item) { return '<li>' + escapeHtml(item.message) + '</li>'; }).join('');
    if (errors.length) { validationSummary.focus(); errors[0].field.scrollIntoView({ block: 'center', behavior: 'smooth' }); }
    return errors.length === 0;
  }

  function review() {
    const address = fulfillment() === 'delivery' ? [form.elements.address.value, form.elements.town.value, form.elements.county.value + ' County'].filter(Boolean).join(', ') : 'Pickup details confirmed after internal fulfillment assignment.';
    page.querySelector('[data-checkout-review]').innerHTML = '<article class="checkout-review__card"><h3 class="heading-4">Contact</h3><p>' + escapeHtml(form.elements.full_name.value) + '<br>' + escapeHtml(form.elements.phone.value) + '<br>' + escapeHtml(form.elements.email.value) + '</p></article><article class="checkout-review__card"><h3 class="heading-4">Fulfillment</h3><p>' + escapeHtml(labelForFulfillment()) + '<br>' + escapeHtml(address) + '</p></article><article class="checkout-review__card"><h3 class="heading-4">Payment</h3><p>' + escapeHtml(labelForPayment()) + ' · display only</p></article>';
  }

  function showStep(value) {
    step = value; panels.forEach(function (panel, index) { panel.hidden = index !== step - 1; });
    indicators.forEach(function (indicator, index) {
      indicator.classList.toggle('is-current', index === step - 1); indicator.classList.toggle('is-complete', index < step - 1);
      if (index === step - 1) indicator.setAttribute('aria-current', 'step'); else indicator.removeAttribute('aria-current');
    });
    back.hidden = step === 1; next.hidden = step === 4; submit.hidden = step !== 4;
    next.textContent = ({ 1: 'Continue to fulfillment', 2: 'Continue to payment', 3: 'Review order' })[step] || '';
    validationSummary.hidden = true; if (step === 4) review(); renderSummary();
    const heading = panels[step - 1].querySelector('legend .heading-2, h2'); if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus(); }
  }

  form.addEventListener('change', function (event) {
    if (event.target.name === 'checkout_mode') page.querySelector('[data-account-placeholder]').hidden = event.target.value === 'guest';
    if (event.target.name === 'fulfillment') configureFulfillment();
    renderSummary();
  });
  form.addEventListener('input', renderSummary);
  next.addEventListener('click', function () { if (validateStep()) showStep(step + 1); });
  back.addEventListener('click', function () { showStep(step - 1); });
  form.addEventListener('submit', function (event) {
    event.preventDefault(); if (!validateStep()) return;
    sessionStorage.setItem(checkoutKey, JSON.stringify({ fulfillment: fulfillment(), payment: payment() }));
    window.location.href = form.dataset.successUrl || '/orders/success/';
  });
  page.querySelector('[data-summary-toggle]').addEventListener('click', function (event) {
    const summary = page.querySelector('[data-checkout-summary]'); const open = summary.classList.toggle('is-open'); event.currentTarget.setAttribute('aria-expanded', String(open));
  });
  page.querySelector('[data-checkout-retry]').addEventListener('click', function () { window.location.href = window.location.pathname; });

  window.setTimeout(function () {
    loading.hidden = true;
    if (page.dataset.stateMode === 'loading') { loading.hidden = false; return; }
    if (page.dataset.stateMode === 'error') { errorState.hidden = false; return; }
    if (page.dataset.stateMode === 'permission') { permission.hidden = false; return; }
    if (page.dataset.stateMode === 'empty' || cartEntries.length === 0) { empty.hidden = false; return; }
    layout.hidden = false; configureFulfillment(); showStep(1);
  }, 220);
}());
