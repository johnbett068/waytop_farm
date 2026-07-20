(function () {
  'use strict';
  const dashboard = document.querySelector('[data-staff-dashboard]');
  const sidebar = document.querySelector('[data-staff-navigation]');
  const menu = document.querySelector('[data-staff-menu]');
  const drawer = document.querySelector('[data-staff-drawer]');
  const dialog = document.querySelector('[data-confirmation-dialog]');
  let drawerTrigger = null;

  function showDashboardState(name) {
    if (!dashboard) return;
    ['loading', 'empty', 'error', 'permission', 'offline', 'success'].forEach(function (state) {
      const node = dashboard.querySelector('[data-dashboard-' + state + ']'); if (node) node.hidden = state !== name;
    });
    const target = dashboard.querySelector('[data-dashboard-' + name + '] h2'); if (name !== 'success' && target) { target.setAttribute('tabindex', '-1'); target.focus(); }
  }
  function openDrawer(trigger) { drawerTrigger = trigger; drawer.hidden = false; document.body.classList.add('staff-overlay-open'); drawer.querySelector('aside').focus(); }
  function closeDrawer() { drawer.hidden = true; document.body.classList.remove('staff-overlay-open'); if (drawerTrigger) drawerTrigger.focus(); }
  function closeMenu() { sidebar.classList.remove('is-open'); menu.setAttribute('aria-expanded', 'false'); }

  if (menu) menu.addEventListener('click', function () { const open = sidebar.classList.toggle('is-open'); menu.setAttribute('aria-expanded', String(open)); });
  document.querySelectorAll('[data-open-drawer]').forEach(function (button) { button.addEventListener('click', function () { openDrawer(button); }); });
  document.querySelectorAll('[data-close-drawer]').forEach(function (button) { button.addEventListener('click', closeDrawer); });
  const confirmationTrigger = document.querySelector('[data-open-confirmation]');
  if (confirmationTrigger && dialog) confirmationTrigger.addEventListener('click', function () { if (dialog.showModal) dialog.showModal(); });
  const dashboardRetry = document.querySelector('[data-dashboard-retry]');
  if (dashboardRetry) dashboardRetry.addEventListener('click', function () { window.location.href = window.location.pathname; });
  document.addEventListener('keydown', function (event) { if (event.key === 'Escape') { if (!drawer.hidden) closeDrawer(); closeMenu(); } });

  if (dashboard) {
    const mode = dashboard.dataset.stateMode;
    showDashboardState(['loading', 'empty', 'error', 'permission', 'offline'].indexOf(mode) >= 0 ? mode : 'success');
  }
}());
