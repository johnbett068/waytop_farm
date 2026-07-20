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
  const searchInput = document.querySelector('[data-search-input]');
  const searchForm = document.querySelector('[data-search-form]');
  const searchSummary = document.querySelector('[data-search-summary]');
  let currentPage = 1;
  let lastFocus = null;

  const selected = function (name) {
    return Array.from(form.querySelectorAll('[name="' + name + '"]:checked')).map(function (input) { return input.value; });
  };

  const visibleCards = function () {
    const categories = selected('category').filter(function (value) { return value !== 'all'; });
    const statuses = selected('status');
    const maximum = Number(form.elements['max-price'].value) || Infinity;
    const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
    return cards.filter(function (card) {
      return (!categories.length || categories.includes(card.dataset.category)) &&
        (!statuses.length || statuses.includes(card.dataset.status)) &&
        Number(card.dataset.price) <= maximum &&
        (!query || card.dataset.name.includes(query));
    });
  };

  const renderPagination = function (total) {
    pagination.replaceChildren();
    const pages = Math.ceil(total / pageSize);
    if (pages <= 1) return;
    for (let page = 1; page <= pages; page += 1) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = page;
      button.setAttribute('aria-label', 'Show product page ' + page);
      if (page === currentPage) button.setAttribute('aria-current', 'page');
      button.addEventListener('click', function () { currentPage = page; update(false); catalog.scrollIntoView({ behavior: 'smooth' }); });
      pagination.appendChild(button);
    }
  };

  const update = function (resetPage) {
    if (resetPage) currentPage = 1;
    error.hidden = true;
    let matches = visibleCards();
    const sortMode = sort.value;
    matches.sort(function (a, b) {
      if (sortMode === 'name-asc') return a.dataset.name.localeCompare(b.dataset.name);
      if (sortMode === 'price-asc') return Number(a.dataset.price) - Number(b.dataset.price);
      if (sortMode === 'price-desc') return Number(b.dataset.price) - Number(a.dataset.price);
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
    if (searchSummary && searchInput) searchSummary.textContent = matches.length + ' results for “' + (searchInput.value || 'all seedlings') + '”.';
  };

  const setAllCategory = function (changed) {
    const all = form.querySelector('[name="category"][value="all"]');
    const others = Array.from(form.querySelectorAll('[name="category"]:not([value="all"])'));
    if (changed === all && all.checked) others.forEach(function (input) { input.checked = false; });
    if (changed !== all && changed.name === 'category') all.checked = !others.some(function (input) { return input.checked; });
  };

  const closeDrawer = function () {
    drawer.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    document.querySelector('[data-filter-open]').setAttribute('aria-expanded', 'false');
    sidebar.appendChild(form);
    document.body.style.overflow = '';
    if (lastFocus) lastFocus.focus();
  };

  const openDrawer = function () {
    lastFocus = document.activeElement;
    mobileMount.appendChild(form);
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    document.querySelector('[data-filter-open]').setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
    panel.focus();
  };

  form.addEventListener('change', function (event) { setAllCategory(event.target); update(true); });
  form.addEventListener('reset', function () { window.setTimeout(function () { update(true); }, 0); });
  sort.addEventListener('change', function () { update(true); });
  document.querySelector('[data-filter-open]').addEventListener('click', openDrawer);
  drawer.querySelectorAll('[data-filter-close]').forEach(function (trigger) { trigger.addEventListener('click', closeDrawer); });
  document.addEventListener('keydown', function (event) {
    if (!drawer.classList.contains('is-open')) return;
    if (event.key === 'Escape') closeDrawer();
    if (event.key === 'Tab') {
      const focusable = panel.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], [tabindex="0"]');
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    }
  });
  if (searchForm) searchForm.addEventListener('submit', function (event) { event.preventDefault(); update(true); });

  const params = new URLSearchParams(window.location.search);
  if (searchInput) searchInput.value = params.get('q') || '';
  loading.hidden = false;
  grid.hidden = true;
  window.setTimeout(function () {
    loading.hidden = true;
    if (params.get('state') === 'error') {
      error.hidden = false;
      grid.hidden = true;
      count.textContent = '0';
    } else {
      update(true);
    }
  }, 180);
}());
