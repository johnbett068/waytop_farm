(function () {
  'use strict';
  const page = document.querySelector('[data-production-page]'); if (!page) return;
  const mode = ['loading', 'empty', 'error', 'permission', 'offline'].indexOf(page.dataset.stateMode) >= 0 ? page.dataset.stateMode : 'success';
  ['loading', 'empty', 'error', 'permission', 'offline', 'success'].forEach(function (state) { const node = page.querySelector('[data-production-' + state + ']'); if (node) node.hidden = state !== mode; });
  if (mode !== 'success') { const heading = page.querySelector('[data-production-' + mode + '] h2'); if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus(); } }
  const retry = page.querySelector('[data-production-retry]'); if (retry) retry.addEventListener('click', function () { window.location.href = window.location.pathname; });

  const tabGroup = page.querySelector('[data-workspace-tabs]');
  if (!tabGroup || mode !== 'success') return;
  const tabs = Array.prototype.slice.call(tabGroup.querySelectorAll('[data-workspace-tab]'));
  const panels = Array.prototype.slice.call(tabGroup.querySelectorAll('[data-workspace-panel]'));
  const validTabs = tabs.map(function (tab) { return tab.dataset.workspaceTab; });

  function activateTab(name, moveFocus, updateHash) {
    if (validTabs.indexOf(name) === -1) name = 'overview';
    tabs.forEach(function (tab) {
      const selected = tab.dataset.workspaceTab === name;
      tab.setAttribute('aria-selected', String(selected));
      tab.setAttribute('tabindex', selected ? '0' : '-1');
      if (selected && moveFocus) tab.focus();
    });
    panels.forEach(function (panel) { panel.hidden = panel.dataset.workspacePanel !== name; });
    if (updateHash && window.history && window.history.replaceState) {
      window.history.replaceState(null, '', '#' + name);
    }
  }

  tabs.forEach(function (tab, index) {
    tab.addEventListener('click', function () { activateTab(tab.dataset.workspaceTab, false, true); });
    tab.addEventListener('keydown', function (event) {
      let targetIndex = null;
      if (event.key === 'ArrowRight') targetIndex = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') targetIndex = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') targetIndex = 0;
      if (event.key === 'End') targetIndex = tabs.length - 1;
      if (targetIndex === null) return;
      event.preventDefault();
      activateTab(tabs[targetIndex].dataset.workspaceTab, true, true);
    });
  });

  activateTab(window.location.hash.replace('#', ''), false, false);
}());
