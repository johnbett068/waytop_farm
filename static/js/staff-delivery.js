(function () {
  'use strict';
  const page = document.querySelector('[data-delivery-page]');
  if (!page) return;
  const fixtures = {
    john: { name: 'John Bett', label: 'Operations Manager', scope: 'All branches', capabilities: ['fulfillment.view', 'fulfillment.assign', 'fulfillment.dispatch', 'fulfillment.record_delivery'] },
    mary: { name: 'Mary Chebet', label: 'Sales Officer', scope: 'Bomet sales scope', capabilities: ['fulfillment.view'] },
    sarah: { name: 'Sarah Wanjiku', label: 'Inventory Clerk', scope: 'Bomet Inventory scope', capabilities: ['fulfillment.view'] },
    amina: { name: 'Amina Noor', label: 'Administrator', scope: 'Configuration only', capabilities: [] }
  };
  const mode = page.dataset.stateMode;
  const select = page.querySelector('[data-delivery-simulator-select]');
  const summary = page.querySelector('[data-delivery-simulator-summary]');
  const live = page.querySelector('[data-delivery-simulator-live]');
  const success = page.querySelector('[data-delivery-success]');
  const permission = page.querySelector('[data-delivery-permission]');
  const storageKey = 'waytop.delivery.authorization-simulation.v1';
  function setState(name) {
    ['loading', 'empty', 'error', 'permission', 'offline', 'success'].forEach(function (value) {
      const node = page.querySelector('[data-delivery-' + value + ']');
      if (node) node.hidden = value !== name;
    });
  }
  function applyFixture(key, announce) {
    const fixture = fixtures[key] || fixtures.john;
    const can = function (capability) { return fixture.capabilities.indexOf(capability) !== -1; };
    summary.textContent = fixture.name + ' · ' + fixture.label + ' · ' + fixture.scope;
    document.querySelectorAll('[data-delivery-capability]').forEach(function (node) { node.hidden = !can(node.dataset.deliveryCapability); });
    document.querySelectorAll('[data-module-capability="fulfillment.view"]').forEach(function (node) { node.hidden = !can('fulfillment.view'); });
    if (mode === 'success') {
      success.hidden = !can('fulfillment.view');
      permission.hidden = can('fulfillment.view');
      if (!can('fulfillment.view') && announce) {
        const heading = permission.querySelector('h2');
        heading.setAttribute('tabindex', '-1');
        heading.focus();
      }
    }
    if (announce) live.textContent = 'Simulation changed to ' + fixture.name + ', ' + fixture.label + '.';
    try { window.localStorage.setItem(storageKey, key); } catch (error) { /* optional preview state */ }
  }
  setState(['loading', 'empty', 'error', 'permission', 'offline'].indexOf(mode) >= 0 ? mode : 'success');
  let selected = 'john';
  try { const stored = window.localStorage.getItem(storageKey); if (fixtures[stored]) selected = stored; } catch (error) { selected = 'john'; }
  select.value = selected;
  applyFixture(selected, false);
  select.addEventListener('change', function () { applyFixture(select.value, true); });
  const retry = page.querySelector('[data-delivery-retry]');
  if (retry) retry.addEventListener('click', function () { window.location.href = window.location.pathname; });
  const toast = page.querySelector('[data-delivery-toast]');
  function notify(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    window.setTimeout(function () { toast.hidden = true; }, 3200);
  }
  document.querySelectorAll('[data-delivery-placeholder]').forEach(function (button) {
    button.addEventListener('click', function () { notify(button.dataset.deliveryPlaceholder); });
  });
  const search = page.querySelector('[data-delivery-search]');
  if (search) search.addEventListener('input', function () {
    const query = search.value.trim().toLowerCase();
    page.querySelectorAll('[data-delivery-job]').forEach(function (row) {
      row.hidden = Boolean(query && row.dataset.search.indexOf(query) === -1);
    });
  });
}());
