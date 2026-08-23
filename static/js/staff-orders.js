(function () {
  'use strict';
  const listPage = document.querySelector('[data-order-management]');
  const detailPage = document.querySelector('[data-order-detail]');

  function showState(page, prefix, name) {
    ['loading', 'empty', 'error', 'permission', 'offline', 'success'].forEach(function (state) {
      const node = page.querySelector('[data-' + prefix + '-' + state + ']'); if (node) node.hidden = state !== name;
    });
    if (name !== 'success') { const heading = page.querySelector('[data-' + prefix + '-' + name + '] h2'); if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus(); } }
  }
  function validMode(mode) { return ['loading', 'empty', 'error', 'permission', 'offline'].indexOf(mode) >= 0 ? mode : 'success'; }

  if (listPage) {
    showState(listPage, 'orders', validMode(listPage.dataset.stateMode));
    const panel = listPage.querySelector('[data-order-filter-panel]'); const toggle = listPage.querySelector('[data-filter-toggle]');
    toggle.addEventListener('click', function () { const open = panel.classList.toggle('is-open'); toggle.setAttribute('aria-expanded', String(open)); });
    function clearFilters() { listPage.querySelectorAll('[data-order-filter], [data-order-query]').forEach(function (field) { if (field.type !== 'date') field.value = ''; }); listPage.querySelector('[data-active-filter-count]').textContent = '0'; listPage.querySelectorAll('[data-order-row], [data-order-card]').forEach(function (item) { item.hidden = false; }); showState(listPage, 'orders', 'success'); }
    listPage.querySelectorAll('[data-clear-filters]').forEach(function (button) { button.addEventListener('click', clearFilters); });
    listPage.querySelector('[data-apply-filters]').addEventListener('click', function () {
      const query = listPage.querySelector('[data-order-query]').value.trim().toLowerCase(); let active = query ? 1 : 0; let visible = 0;
      const selectFilters = Array.from(listPage.querySelectorAll('select[data-order-filter]')).filter(function (field) { if (field.value) active += 1; return field.value; });
      listPage.querySelectorAll('[data-order-row]').forEach(function (row) {
        const matchesQuery = !query || row.dataset.search.indexOf(query) >= 0;
        const matchesFilters = selectFilters.every(function (field) { return row.dataset[field.dataset.orderFilter] === field.value; });
        row.hidden = !(matchesQuery && matchesFilters); if (!row.hidden) visible += 1;
      });
      listPage.querySelectorAll('[data-order-card]').forEach(function (card) {
        const matchesQuery = !query || card.dataset.search.indexOf(query) >= 0;
        const matchesFilters = selectFilters.every(function (field) { return card.dataset[field.dataset.orderFilter] === field.value; });
        card.hidden = !(matchesQuery && matchesFilters);
      });
      listPage.querySelector('[data-active-filter-count]').textContent = String(active);
      if (!visible) showState(listPage, 'orders', 'empty');
    });
    listPage.querySelector('[data-orders-retry]').addEventListener('click', function () { window.location.href = window.location.pathname; });
  }

  if (detailPage) {
    showState(detailPage, 'order-detail', validMode(detailPage.dataset.stateMode));
    const menu = detailPage.querySelector('[data-action-menu]'); const toggle = detailPage.querySelector('[data-action-menu-toggle]'); const dialog = document.querySelector('[data-order-action-dialog]');
    toggle.addEventListener('click', function () { const open = menu.hidden; menu.hidden = !open; toggle.setAttribute('aria-expanded', String(open)); });
    const labels = { fulfill: 'Mark order fulfilled?', cancel: 'Request authorized cancellation?' };
    menu.querySelectorAll('[data-order-command]').forEach(function (button) { button.addEventListener('click', function () { menu.hidden = true; toggle.setAttribute('aria-expanded', 'false'); dialog.querySelector('[data-order-command-title]').textContent = labels[button.dataset.orderCommand]; if (dialog.showModal) dialog.showModal(); }); });
    detailPage.querySelector('[data-orders-retry]').addEventListener('click', function () { window.location.href = window.location.pathname; });
    document.addEventListener('click', function (event) { if (!menu.hidden && !event.target.closest('[data-action-menu], [data-action-menu-toggle]')) { menu.hidden = true; toggle.setAttribute('aria-expanded', 'false'); } });
  }
}());
