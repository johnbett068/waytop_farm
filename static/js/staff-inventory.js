(function () {
  'use strict';
  const page = document.querySelector('[data-inventory-page]');
  if (!page) return;

  const fixtures = {
    sarah: {
      name: 'Sarah Wanjiku', role: 'Inventory Clerk', scope: 'Bomet Main Store',
      capabilities: ['inventory.view', 'inventory.receive', 'inventory.release', 'inventory.adjust', 'inventory.transfer', 'inventory.dispatch_transfer', 'inventory.receive_transfer', 'inventory.count']
    },
    john: {
      name: 'John Bett', role: 'Operations Manager', scope: 'All branches',
      capabilities: ['inventory.view', 'inventory.receive', 'inventory.release', 'inventory.adjust', 'inventory.approve_adjustment', 'inventory.transfer', 'inventory.approve_transfer', 'inventory.dispatch_transfer', 'inventory.receive_transfer', 'inventory.count', 'inventory.approve_count_variance', 'inventory.export']
    },
    peter: {
      name: 'Peter Kiptoo', role: 'Nursery Supervisor', scope: 'Bomet Nursery',
      capabilities: ['inventory.view']
    },
    amina: {
      name: 'Amina Noor', role: 'Administrator', scope: 'Administrative global scope',
      capabilities: []
    }
  };
  const storageKey = 'waytop.inventory.authorization-simulation.v1';
  const select = page.querySelector('[data-simulator-select]');
  const summary = page.querySelector('[data-simulator-summary]');
  const live = page.querySelector('[data-simulator-live]');
  const success = page.querySelector('[data-inventory-success]');
  const permission = page.querySelector('[data-inventory-permission]');
  const configuredMode = page.dataset.stateMode;

  function setState(name) {
    ['loading', 'empty', 'error', 'permission', 'offline', 'success'].forEach(function (state) {
      const node = page.querySelector('[data-inventory-' + state + ']');
      if (node) node.hidden = state !== name;
    });
  }

  function applyFixture(key, announce) {
    const fixture = fixtures[key] || fixtures.sarah;
    const allowed = function (capability) { return fixture.capabilities.indexOf(capability) !== -1; };
    summary.textContent = fixture.name + ' · ' + fixture.role + ' · ' + fixture.scope;
    document.querySelectorAll('[data-capability]').forEach(function (node) {
      node.hidden = !allowed(node.dataset.capability);
    });
    document.querySelectorAll('[data-module-capability]').forEach(function (node) {
      node.hidden = !allowed(node.dataset.moduleCapability);
    });
    if (configuredMode === 'success') {
      if (allowed('inventory.view')) {
        permission.hidden = true;
        success.hidden = false;
      } else {
        success.hidden = true;
        permission.hidden = false;
        const heading = permission.querySelector('h2');
        if (announce && heading) { heading.setAttribute('tabindex', '-1'); heading.focus(); }
      }
    }
    if (announce) live.textContent = 'Simulation changed to ' + fixture.name + ', ' + fixture.role + '.';
    try { window.localStorage.setItem(storageKey, key); } catch (error) { /* storage is optional */ }
  }

  const validModes = ['loading', 'empty', 'error', 'permission', 'offline'];
  setState(validModes.indexOf(configuredMode) >= 0 ? configuredMode : 'success');
  let selected = 'sarah';
  try { selected = fixtures[window.localStorage.getItem(storageKey)] ? window.localStorage.getItem(storageKey) : 'sarah'; } catch (error) { selected = 'sarah'; }
  select.value = selected;
  applyFixture(selected, false);
  select.addEventListener('change', function () { applyFixture(select.value, true); });

  const retry = page.querySelector('[data-inventory-retry]');
  if (retry) retry.addEventListener('click', function () { window.location.href = window.location.pathname; });

  const tabRoot = page.querySelector('[data-inventory-tabs]');
  if (tabRoot) {
    const tabs = Array.prototype.slice.call(tabRoot.querySelectorAll('[data-inventory-tab]'));
    const panels = Array.prototype.slice.call(tabRoot.querySelectorAll('[data-inventory-panel]'));
    function activate(name, focus) {
      tabs.forEach(function (tab) {
        const active = tab.dataset.inventoryTab === name;
        tab.setAttribute('aria-selected', String(active));
        tab.setAttribute('tabindex', active ? '0' : '-1');
        if (active && focus) tab.focus();
      });
      panels.forEach(function (panel) { panel.hidden = panel.dataset.inventoryPanel !== name; });
      if (window.history && window.history.replaceState) window.history.replaceState(null, '', '#' + name);
    }
    tabs.forEach(function (tab, index) {
      tab.addEventListener('click', function () { activate(tab.dataset.inventoryTab, false); });
      tab.addEventListener('keydown', function (event) {
        let next = null;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        if (next === null) return;
        event.preventDefault();
        activate(tabs[next].dataset.inventoryTab, true);
      });
    });
    const hash = window.location.hash.replace('#', '');
    if (tabs.some(function (tab) { return tab.dataset.inventoryTab === hash; })) activate(hash, false);
  }
}());
