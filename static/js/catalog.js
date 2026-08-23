(function () {
  'use strict';

  const catalog = document.querySelector('[data-catalog]');
  if (!catalog) return;

  const grid = catalog.querySelector('[data-product-grid]');
  const cards = Array.from(catalog.querySelectorAll('[data-product-card]'));
  const form = catalog.querySelector('#catalog-filters');
  const sidebar = catalog.querySelector('.catalog-sidebar');
  const drawer = catalog.querySelector('.filter-drawer');
  const panel = drawer.querySelector('.filter-drawer__panel');
  const mobileMount = drawer.querySelector('[data-mobile-filters]');
  const count = catalog.querySelector('[data-result-count]');
  const empty = catalog.querySelector('[data-empty-state]');
  const error = catalog.querySelector('[data-error-state]');
  const loading = catalog.querySelector('[data-loading-state]');
  const pagination = catalog.querySelector('[data-pagination]');
  const sort = catalog.querySelector('[data-sort]');
  const pageSize = Number(catalog.dataset.pageSize) || 6;
  let currentPage = 1;
  let lastFocus = null;

  function cardPrice(card) {
    return card.dataset.price === '' ? Infinity : Number(card.dataset.price);
  }

  function visibleCards() {
    const maximum = Number(form.elements['max-price'].value) || Infinity;
    return cards.filter(function (card) { return cardPrice(card) <= maximum; });
  }

  function renderPagination(total) {
    pagination.replaceChildren();
    const pages = Math.ceil(total / pageSize);
    if (pages <= 1) return;
    for (let page = 1; page <= pages; page += 1) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = page;
      button.setAttribute('aria-label', 'Show product page ' + page);
      if (page === currentPage) button.setAttribute('aria-current', 'page');
      button.addEventListener('click', function () {
        currentPage = page;
        update(false);
        catalog.scrollIntoView({ behavior: 'smooth' });
      });
      pagination.appendChild(button);
    }
  }

  function update(resetPage) {
    if (resetPage) currentPage = 1;
    error.hidden = true;
    const matches = visibleCards();
    const sortMode = sort.value;
    matches.sort(function (a, b) {
      if (sortMode === 'name-asc') return a.dataset.name.localeCompare(b.dataset.name);
      if (sortMode === 'price-asc') return cardPrice(a) - cardPrice(b);
      if (sortMode === 'price-desc') return cardPrice(b) - cardPrice(a);
      return cards.indexOf(a) - cards.indexOf(b);
    });
    matches.forEach(function (card) { grid.appendChild(card); });
    const start = (currentPage - 1) * pageSize;
    cards.forEach(function (card) { card.hidden = true; });
    matches.slice(start, start + pageSize).forEach(function (card) { card.hidden = false; });
    count.textContent = matches.length;
    empty.hidden = matches.length !== 0;
    grid.hidden = matches.length === 0;
    renderPagination(matches.length);
  }

  function closeDrawer() {
    drawer.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    document.querySelector('[data-filter-open]').setAttribute('aria-expanded', 'false');
    sidebar.appendChild(form);
    document.body.style.overflow = '';
    if (lastFocus) lastFocus.focus();
  }

  function openDrawer() {
    lastFocus = document.activeElement;
    mobileMount.appendChild(form);
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    document.querySelector('[data-filter-open]').setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
    panel.focus();
  }

  form.addEventListener('change', function () { update(true); });
  form.addEventListener('reset', function () { window.setTimeout(function () { update(true); }, 0); });
  sort.addEventListener('change', function () { update(true); });
  document.querySelector('[data-filter-open]').addEventListener('click', openDrawer);
  drawer.querySelectorAll('[data-filter-close]').forEach(function (trigger) { trigger.addEventListener('click', closeDrawer); });
  document.addEventListener('keydown', function (event) {
    if (!drawer.classList.contains('is-open')) return;
    if (event.key === 'Escape') closeDrawer();
    if (event.key !== 'Tab') return;
    const focusable = panel.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], [tabindex="0"]');
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  loading.hidden = false;
  grid.hidden = true;
  window.setTimeout(function () {
    loading.hidden = true;
    if (new URLSearchParams(window.location.search).get('state') === 'error') {
      error.hidden = false;
      count.textContent = '0';
    } else {
      update(true);
    }
  }, 180);
}());
