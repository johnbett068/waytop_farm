(function () {
  'use strict';
  const confirmation = document.querySelector('[data-order-confirmation]');
  const page = document.querySelector('[data-order-tracking]');
  const validOrder = 'WTF-260716-1042';
  const validPhone = '+254724853914';

  if (confirmation) {
    const state = confirmation.dataset.stateMode;
    confirmation.querySelector('[data-confirmation-success]').hidden = state !== 'success';
    ['loading', 'empty', 'expired', 'error', 'permission'].forEach(function (name) {
      const node = confirmation.querySelector('[data-confirmation-' + name + ']'); node.hidden = state !== name;
    });
    const focusTarget = state === 'success' ? confirmation.querySelector('h1') : confirmation.querySelector('[data-confirmation-' + state + '] h2');
    if (focusTarget) { focusTarget.setAttribute('tabindex', '-1'); focusTarget.focus(); }
  }
  if (!page) return;

  const form = page.querySelector('[data-tracking-form]');
  const states = {
    empty: page.querySelector('[data-tracking-empty]'), loading: page.querySelector('[data-tracking-loading]'),
    notfound: page.querySelector('[data-tracking-not-found]'), error: page.querySelector('[data-tracking-error]'),
    expired: page.querySelector('[data-tracking-expired]'), permission: page.querySelector('[data-tracking-permission]'),
    success: page.querySelector('[data-tracking-result]')
  };

  function normalizeOrder(value) { return value.trim().toUpperCase().replace(/\s+/g, ''); }
  function normalizePhone(value) { return value.trim().replace(/[\s-]/g, ''); }
  function show(name, focus) {
    Object.keys(states).forEach(function (key) { states[key].hidden = key !== name; });
    if (focus) {
      const target = states[name].querySelector('h1, h2, [tabindex="-1"]') || states[name];
      target.setAttribute('tabindex', '-1'); target.focus();
    }
  }
  function validate() {
    const order = form.elements.order_number; const phone = form.elements.phone;
    const orderValid = /^WTF-\d{6}-\d{4}$/.test(normalizeOrder(order.value));
    const phoneValid = /^\+254\d{9}$/.test(normalizePhone(phone.value));
    order.setAttribute('aria-invalid', String(!orderValid)); phone.setAttribute('aria-invalid', String(!phoneValid));
    form.querySelector('#tracking-order-error').textContent = orderValid ? '' : 'Enter an order number such as WTF-260716-1042.';
    form.querySelector('#tracking-phone-error').textContent = phoneValid ? '' : 'Enter a Kenyan number such as +254 724 853 914.';
    form.querySelector('[data-tracking-validation]').hidden = orderValid && phoneValid;
    if (!orderValid || !phoneValid) { form.querySelector('[data-tracking-validation]').focus(); return false; }
    return true;
  }
  function lookup() {
    show('loading', false);
    window.setTimeout(function () {
      const matches = normalizeOrder(form.elements.order_number.value) === validOrder && normalizePhone(form.elements.phone.value) === validPhone;
      show(matches ? 'success' : 'notfound', true);
    }, 360);
  }

  form.addEventListener('submit', function (event) { event.preventDefault(); if (validate()) lookup(); });
  page.querySelectorAll('[data-try-again]').forEach(function (button) { button.addEventListener('click', function () { show('empty', false); form.elements.order_number.focus(); }); });
  page.querySelector('[data-tracking-retry]').addEventListener('click', function () { window.location.href = window.location.pathname; });
  form.addEventListener('input', function (event) { event.target.removeAttribute('aria-invalid'); const error = event.target.parentElement.querySelector('[data-tracking-field-error]'); if (error) error.textContent = ''; });

  const initial = page.dataset.stateMode;
  if (initial === 'loading') show('loading', false);
  else if (initial === 'not-found') show('notfound', true);
  else if (initial === 'error') show('error', true);
  else if (initial === 'expired') show('expired', true);
  else if (initial === 'permission') show('permission', true);
  else if (initial === 'success') show('success', false);
  else show('empty', false);
}());
