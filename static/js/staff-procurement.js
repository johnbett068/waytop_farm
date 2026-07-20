(function () {
  'use strict';
  const page = document.querySelector('[data-procurement-page]');
  if (!page) return;
  const fixtures = {
    mary: { name: 'Mary Chebet', role: 'Sales Officer', scope: 'Bomet Town', capabilities: ['procurement.view', 'procurement.create_request'] },
    peter: { name: 'Peter Kiptoo', role: 'Nursery Supervisor', scope: 'Bomet Nursery', capabilities: ['procurement.view', 'procurement.create_request', 'procurement.approve_request'] },
    sarah: { name: 'Sarah Wanjiku', role: 'Inventory Clerk', scope: 'Bomet Main Store', capabilities: ['procurement.view', 'procurement.create_request', 'procurement.record_delivery'] },
    john: { name: 'John Bett', role: 'Operations Manager', scope: 'All branches', capabilities: ['procurement.view', 'procurement.create_request', 'procurement.approve_request', 'procurement.manage_supplier', 'procurement.manage_quotation', 'procurement.create_order', 'procurement.approve_order', 'procurement.issue_order', 'procurement.record_delivery', 'procurement.view_spend', 'procurement.export'] },
    amina: { name: 'Amina Noor', role: 'Administrator', scope: 'Administrative global scope', capabilities: ['procurement.view', 'procurement.manage_supplier', 'procurement.approve_order', 'procurement.view_spend'] },
    jane: { name: 'Jane Atieno', role: 'Cashier', scope: 'Bomet Register BMT-01', capabilities: [] }
  };
  const key = 'waytop.procurement.authorization-simulation.v1';
  const select = page.querySelector('[data-procurement-simulator-select]');
  const summary = page.querySelector('[data-procurement-simulator-summary]');
  const live = page.querySelector('[data-procurement-simulator-live]');
  const success = page.querySelector('[data-procurement-success]');
  const permission = page.querySelector('[data-procurement-permission]');
  const mode = page.dataset.stateMode;
  function state(name) { ['loading', 'empty', 'error', 'permission', 'offline', 'success'].forEach(function (value) { const node = page.querySelector('[data-procurement-' + value + ']'); if (node) node.hidden = value !== name; }); }
  function apply(name, announce) {
    const fixture = fixtures[name] || fixtures.mary;
    const can = function (capability) { return fixture.capabilities.indexOf(capability) !== -1; };
    summary.textContent = fixture.name + ' · ' + fixture.role + ' · ' + fixture.scope;
    document.querySelectorAll('[data-procurement-capability]').forEach(function (node) { node.hidden = !can(node.dataset.procurementCapability); });
    document.querySelectorAll('[data-module-capability="procurement.view"]').forEach(function (node) { node.hidden = !can('procurement.view'); });
    if (mode === 'success') {
      success.hidden = !can('procurement.view'); permission.hidden = can('procurement.view');
      if (!can('procurement.view') && announce) { const heading = permission.querySelector('h2'); heading.setAttribute('tabindex', '-1'); heading.focus(); }
    }
    if (announce) live.textContent = 'Simulation changed to ' + fixture.name + ', ' + fixture.role + '.';
    try { window.localStorage.setItem(key, name); } catch (error) { /* optional */ }
  }
  state(['loading', 'empty', 'error', 'permission', 'offline'].indexOf(mode) >= 0 ? mode : 'success');
  let selected = 'mary';
  try { const stored = window.localStorage.getItem(key); if (fixtures[stored]) selected = stored; } catch (error) { selected = 'mary'; }
  select.value = selected; apply(selected, false); select.addEventListener('change', function () { apply(select.value, true); });
  const retry = page.querySelector('[data-procurement-retry]'); if (retry) retry.addEventListener('click', function () { window.location.href = window.location.pathname; });
  const tabRoot = page.querySelector('[data-procurement-tabs]');
  if (tabRoot) {
    const tabs = Array.prototype.slice.call(tabRoot.querySelectorAll('[data-procurement-tab]')); const panels = Array.prototype.slice.call(tabRoot.querySelectorAll('[data-procurement-panel]'));
    function activate(name, focus) { tabs.forEach(function (tab) { const active = tab.dataset.procurementTab === name; tab.setAttribute('aria-selected', String(active)); tab.setAttribute('tabindex', active ? '0' : '-1'); if (active && focus) tab.focus(); }); panels.forEach(function (panel) { panel.hidden = panel.dataset.procurementPanel !== name; }); if (window.history && window.history.replaceState) window.history.replaceState(null, '', '#' + name); }
    tabs.forEach(function (tab, index) { tab.addEventListener('click', function () { activate(tab.dataset.procurementTab, false); }); tab.addEventListener('keydown', function (event) { let next = null; if (event.key === 'ArrowRight') next = (index + 1) % tabs.length; if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length; if (event.key === 'Home') next = 0; if (event.key === 'End') next = tabs.length - 1; if (next === null) return; event.preventDefault(); activate(tabs[next].dataset.procurementTab, true); }); });
    const hash = window.location.hash.replace('#', ''); if (tabs.some(function (tab) { return tab.dataset.procurementTab === hash; })) activate(hash, false);
  }
}());
