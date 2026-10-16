(function () {
  'use strict';

  const catalogNode = document.getElementById('commerce-catalog-data');
  if (!catalogNode) return;

  const catalog = JSON.parse(catalogNode.textContent || '[]');
  const products = new Map();
  const saleUnits = new Map();
  catalog.forEach(function (product) {
    products.set(product.slug, product);
    product.sale_units.forEach(function (unit) { saleUnits.set(unit.key, { product: product, unit: unit }); });
  });
  const storageKey = 'waytop-commerce-v1';
  let state = { wishlist: [], cart: {} };
  let storageAvailable = true;
  let lastDrawerTrigger = null;

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, function (character) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character];
    });
  }

  function money(currency, amount) {
    return currency + ' ' + Number(amount).toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function safeKey(value) {
    return typeof value === 'string' && value.length <= 240 && !['__proto__', 'constructor', 'prototype'].includes(value);
  }

  function sanitize(raw) {
    const clean = { wishlist: [], cart: {} };
    if (raw && Array.isArray(raw.wishlist)) {
      clean.wishlist = raw.wishlist.filter(function (slug, index, list) { return safeKey(slug) && list.indexOf(slug) === index; });
    }
    if (raw && raw.cart && typeof raw.cart === 'object') {
      Object.keys(raw.cart).forEach(function (key) {
        if (!safeKey(key)) return;
        const item = raw.cart[key] || {};
        clean.cart[key] = { quantity: Math.min(99, Math.max(1, parseInt(item.quantity, 10) || 1)) };
      });
    }
    return clean;
  }

  function load() {
    try {
      state = sanitize(JSON.parse(window.localStorage.getItem(storageKey) || '{}'));
      save();
    } catch (error) {
      storageAvailable = false;
      state = sanitize(state);
    }
  }

  function save() {
    try { window.localStorage.setItem(storageKey, JSON.stringify(state)); }
    catch (error) { storageAvailable = false; }
  }

  function cartEntries() {
    return Object.keys(state.cart).map(function (key) {
      const current = saleUnits.get(key);
      return { key: key, item: state.cart[key], current: current || null };
    });
  }

  function cartQuantity() {
    return cartEntries().reduce(function (total, entry) { return total + entry.item.quantity; }, 0);
  }

  function cartTotal() {
    return cartEntries().reduce(function (total, entry) {
      return total + (entry.current ? Number(entry.current.unit.amount) * entry.item.quantity : 0);
    }, 0);
  }

  function toast(message, actionLabel, action) {
    const region = document.querySelector('[data-toast-region]');
    if (!region) return;
    const node = document.createElement('div');
    node.className = 'commerce-toast';
    node.innerHTML = '<p>' + escapeHtml(message) + '</p>' + (actionLabel ? '<button type="button">' + escapeHtml(actionLabel) + '</button>' : '');
    if (actionLabel) node.querySelector('button').addEventListener('click', function () { action(); node.remove(); });
    region.appendChild(node);
    window.setTimeout(function () { if (node.isConnected) node.remove(); }, 5200);
  }

  function updateCounters() {
    const wishlistCount = state.wishlist.length;
    const cartCount = cartQuantity();
    document.querySelectorAll('[data-wishlist-count]').forEach(function (node) { node.textContent = wishlistCount; node.hidden = wishlistCount === 0; });
    document.querySelectorAll('[data-cart-count]').forEach(function (node) { node.textContent = cartCount; node.hidden = cartCount === 0; });
    document.querySelectorAll('[data-wishlist-link]').forEach(function (node) { node.setAttribute('aria-label', 'Wishlist, ' + wishlistCount + ' items'); });
    document.querySelectorAll('[data-cart-open]').forEach(function (node) { node.setAttribute('aria-label', 'Open cart, ' + cartCount + ' items'); });
  }

  function updateProductActions() {
    document.querySelectorAll('[data-wishlist-toggle]').forEach(function (button) {
      const slug = button.dataset.wishlistToggle;
      const selected = state.wishlist.includes(slug);
      const product = products.get(slug);
      button.setAttribute('aria-pressed', String(selected));
      button.setAttribute('aria-label', (selected ? 'Remove ' : 'Save ') + (product ? product.name : 'unavailable item') + (selected ? ' from wishlist' : ' to wishlist'));
      const symbol = button.querySelector('[aria-hidden="true"]');
      if (symbol) symbol.textContent = selected ? '♥' : '♡';
    });
  }

  function persistAndRender() {
    save(); updateCounters(); updateProductActions(); renderMiniCart(); renderWishlistPage(); renderCartPage();
  }

  function toggleWishlist(slug) {
    const index = state.wishlist.indexOf(slug);
    if (index !== -1) {
      state.wishlist.splice(index, 1); persistAndRender(); toast('Item removed from your wishlist.'); return;
    }
    const product = products.get(slug);
    if (!product) { toast('This saved product is no longer in the published catalog.'); return; }
    state.wishlist.push(slug); persistAndRender(); toast(product.name + ' saved to your wishlist.');
  }

  function addToCart(key) {
    const current = saleUnits.get(key);
    if (!current) { toast('This sale unit or price is no longer published.'); return; }
    if (state.cart[key]) state.cart[key].quantity = Math.min(99, state.cart[key].quantity + 1);
    else state.cart[key] = { quantity: 1 };
    persistAndRender(); toast(current.product.name + ' (' + current.unit.name + ') added to your cart.');
  }

  function removeCart(key) {
    const previous = state.cart[key];
    if (!previous) return;
    delete state.cart[key]; persistAndRender();
    toast('Item removed from your cart.', 'Undo', function () { state.cart[key] = previous; persistAndRender(); });
  }

  function productImageMarkup(product, className) {
    const image = product.main_image;
    if (!image || !image.url) return '<div class="' + className + ' commerce-product-placeholder" aria-hidden="true">WT</div>';
    return '<div class="' + className + '"><img src="' + escapeHtml(image.url) + '" alt="' + escapeHtml(image.alt || product.name) + '" loading="lazy"></div>';
  }

  function miniCartMarkup(entry) {
    if (!entry.current) {
      return '<article class="mini-cart-item mini-cart-item--stale"><div class="commerce-product-placeholder" aria-hidden="true">?</div><div><h3 class="heading-4">Unavailable catalog item</h3><p>' + entry.item.quantity + ' × saved item</p><p class="commerce-unavailable">Remove or revisit the catalog.</p></div><button class="commerce-icon-button" type="button" data-cart-remove="' + escapeHtml(entry.key) + '" aria-label="Remove unavailable item"><span aria-hidden="true">×</span></button></article>';
    }
    const product = entry.current.product; const unit = entry.current.unit;
    return '<article class="mini-cart-item">' + productImageMarkup(product, 'mini-cart-item__media') + '<div><h3 class="heading-4"><a href="' + escapeHtml(product.product_url) + '">' + escapeHtml(product.name) + '</a></h3><p>' + entry.item.quantity + ' × ' + escapeHtml(unit.name) + '</p><p class="mini-cart-item__price">' + money(unit.currency, Number(unit.amount) * entry.item.quantity) + '</p></div><button class="commerce-icon-button" type="button" data-cart-remove="' + escapeHtml(entry.key) + '" aria-label="Remove ' + escapeHtml(product.name) + '"><span aria-hidden="true">×</span></button></article>';
  }

  function renderMiniCart() {
    const container = document.querySelector('[data-mini-cart-items]'); if (!container) return;
    const entries = cartEntries();
    container.innerHTML = entries.map(miniCartMarkup).join('');
    document.querySelector('[data-mini-cart-empty]').hidden = entries.length !== 0;
    document.querySelector('[data-mini-cart-footer]').hidden = entries.length === 0;
    const total = document.querySelector('[data-mini-cart-total]'); if (total) total.textContent = money('KES', cartTotal());
  }

  function wishlistMarkup(slug) {
    const product = products.get(slug);
    if (!product) {
      return '<article class="wishlist-card"><div class="wishlist-card__media commerce-product-placeholder" aria-hidden="true">?</div><div class="wishlist-card__body"><h2 class="heading-3">Unavailable catalog item</h2><p class="commerce-unavailable">The saved product is no longer in the published catalog. It has not been recreated.</p><button class="btn btn--outline" type="button" data-wishlist-toggle="' + escapeHtml(slug) + '">Remove saved item</button></div></article>';
    }
    const first = product.sale_units[0];
    const price = first ? money(first.currency, first.amount) + ' per ' + first.name : 'No current price';
    return '<article class="wishlist-card" data-commerce-product="' + escapeHtml(product.slug) + '">' + productImageMarkup(product, 'wishlist-card__media') + '<button class="commerce-heart" type="button" data-wishlist-toggle="' + escapeHtml(product.slug) + '" aria-pressed="true" aria-label="Remove ' + escapeHtml(product.name) + ' from wishlist"><span aria-hidden="true">♥</span></button><div class="wishlist-card__body"><h2 class="heading-3"><a href="' + escapeHtml(product.product_url) + '">' + escapeHtml(product.name) + '</a></h2><p class="wishlist-card__meta">' + escapeHtml(price) + '</p><div class="wishlist-card__actions"><a class="btn btn--outline" href="' + escapeHtml(product.product_url) + '">Choose sale unit</a></div></div></article>';
  }

  function renderWishlistPage() {
    const page = document.querySelector('[data-commerce-page="wishlist"]'); if (!page || page.dataset.ready !== 'true') return;
    const grid = page.querySelector('[data-wishlist-grid]'); const empty = page.querySelector('[data-wishlist-empty]');
    grid.innerHTML = state.wishlist.map(wishlistMarkup).join(''); grid.hidden = state.wishlist.length === 0; empty.hidden = state.wishlist.length !== 0;
    page.querySelector('[data-clear-wishlist]').hidden = state.wishlist.length === 0; updateProductActions();
  }

  function cartMarkup(entry) {
    if (!entry.current) {
      return '<article class="cart-item" data-cart-item="' + escapeHtml(entry.key) + '"><div class="cart-item__media commerce-product-placeholder" aria-hidden="true">?</div><div class="cart-item__content"><div class="cart-item__top"><div><h2 class="heading-3">Unavailable catalog item</h2><p class="commerce-unavailable">This saved identifier no longer resolves to a published product, active sale unit, and current price.</p></div><button class="commerce-text-button" type="button" data-cart-remove="' + escapeHtml(entry.key) + '">Remove</button></div></div></article>';
    }
    const product = entry.current.product; const unit = entry.current.unit;
    return '<article class="cart-item" data-cart-item="' + escapeHtml(entry.key) + '">' + productImageMarkup(product, 'cart-item__media') + '<div class="cart-item__content"><div class="cart-item__top"><div><h2 class="heading-3"><a href="' + escapeHtml(product.product_url) + '">' + escapeHtml(product.name) + '</a></h2><p class="cart-item__unit">' + money(unit.currency, unit.amount) + ' per ' + escapeHtml(unit.name) + '</p></div><button class="commerce-text-button" type="button" data-cart-remove="' + escapeHtml(entry.key) + '">Remove</button></div><div class="cart-item__controls"><label class="commerce-field"><span>Quantity</span><span class="quantity-control"><button type="button" data-quantity-action="decrease" aria-label="Decrease quantity">−</button><input type="number" min="1" max="99" value="' + entry.item.quantity + '" data-cart-quantity aria-label="Quantity for ' + escapeHtml(product.name) + '"><button type="button" data-quantity-action="increase" aria-label="Increase quantity">+</button></span></label></div><div class="cart-item__footer"><span class="small">' + escapeHtml(unit.base_quantity + ' ' + unit.base_unit + ' per ' + unit.name) + '</span><strong class="cart-item__line-total">' + money(unit.currency, Number(unit.amount) * entry.item.quantity) + '</strong></div></div></article>';
  }

  function renderCartPage() {
    const page = document.querySelector('[data-commerce-page="cart"]'); if (!page || page.dataset.ready !== 'true') return;
    const entries = cartEntries(); const items = page.querySelector('[data-cart-items]');
    items.innerHTML = entries.map(cartMarkup).join('');
    page.querySelector('[data-cart-layout]').hidden = entries.length === 0; page.querySelector('[data-cart-empty]').hidden = entries.length !== 0; page.querySelector('[data-clear-cart]').hidden = entries.length === 0;
    const count = cartQuantity(); page.querySelector('[data-summary-items]').textContent = count + (count === 1 ? ' item' : ' items');
    page.querySelector('[data-summary-subtotal]').textContent = money('KES', cartTotal()); page.querySelector('[data-summary-total]').textContent = money('KES', cartTotal());
  }

  function preparePage(page) {
    const loading = page.querySelector('[data-commerce-loading]'); const error = page.querySelector('[data-commerce-error]');
    if (page.dataset.stateMode === 'loading') return;
    window.setTimeout(function () {
      loading.hidden = true;
      if (page.dataset.stateMode === 'error') { error.hidden = false; return; }
      page.dataset.ready = 'true'; renderWishlistPage(); renderCartPage();
    }, 220);
  }

  function updateOfflineState() {
    document.querySelectorAll('[data-commerce-page]').forEach(function (page) {
      let note = page.querySelector('.commerce-offline-note');
      if (!navigator.onLine && !note) {
        note = document.createElement('div'); note.className = 'commerce-offline-note'; note.innerHTML = '<strong>Offline</strong><span>Saved browser items remain visible. Current catalog data cannot be refreshed.</span>';
        page.querySelector('.commerce-page__header').after(note);
      } else if (navigator.onLine && note) note.remove();
    });
  }

  function openCart(trigger) {
    const drawer = document.getElementById('mini-cart'); if (!drawer) return;
    lastDrawerTrigger = trigger; drawer.classList.add('is-open'); drawer.setAttribute('aria-hidden', 'false'); document.body.classList.add('has-commerce-drawer');
    document.querySelectorAll('[data-cart-open]').forEach(function (button) { button.setAttribute('aria-expanded', 'true'); });
    drawer.querySelector('.commerce-drawer__panel').focus();
  }

  function closeCart() {
    const drawer = document.getElementById('mini-cart'); if (!drawer) return;
    drawer.classList.remove('is-open'); drawer.setAttribute('aria-hidden', 'true'); document.body.classList.remove('has-commerce-drawer');
    document.querySelectorAll('[data-cart-open]').forEach(function (button) { button.setAttribute('aria-expanded', 'false'); });
    if (lastDrawerTrigger) lastDrawerTrigger.focus();
  }

  document.addEventListener('click', function (event) {
    const wishlist = event.target.closest('[data-wishlist-toggle]'); if (wishlist) { toggleWishlist(wishlist.dataset.wishlistToggle); return; }
    const add = event.target.closest('[data-cart-add]'); if (add && !add.disabled) { addToCart(add.dataset.cartAdd); return; }
    const remove = event.target.closest('[data-cart-remove]'); if (remove) { removeCart(remove.dataset.cartRemove); return; }
    const open = event.target.closest('[data-cart-open]'); if (open) { openCart(open); return; }
    if (event.target.closest('[data-cart-close]')) { closeCart(); return; }
    const quantityAction = event.target.closest('[data-quantity-action]');
    if (quantityAction) {
      const row = quantityAction.closest('[data-cart-item]'); const key = row.dataset.cartItem; const delta = quantityAction.dataset.quantityAction === 'increase' ? 1 : -1;
      if (state.cart[key]) state.cart[key].quantity = Math.min(99, Math.max(1, state.cart[key].quantity + delta));
      persistAndRender(); return;
    }
    if (event.target.closest('[data-clear-wishlist]')) { state.wishlist = []; persistAndRender(); return; }
    if (event.target.closest('[data-clear-cart]')) { state.cart = {}; persistAndRender(); return; }
    if (event.target.closest('[data-commerce-retry]')) { const url = new URL(window.location.href); url.searchParams.delete('state'); window.location.href = url.toString(); }
  });

  document.addEventListener('change', function (event) {
    const row = event.target.closest('[data-cart-item]'); if (!row || !state.cart[row.dataset.cartItem]) return;
    if (event.target.matches('[data-cart-quantity]')) state.cart[row.dataset.cartItem].quantity = Math.min(99, Math.max(1, parseInt(event.target.value, 10) || 1));
    persistAndRender();
  });

  document.addEventListener('keydown', function (event) {
    const drawer = document.getElementById('mini-cart'); if (!drawer || !drawer.classList.contains('is-open')) return;
    if (event.key === 'Escape') { closeCart(); return; }
    if (event.key !== 'Tab') return;
    const focusable = drawer.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex="0"]');
    const first = focusable[0]; const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  window.addEventListener('storage', function (event) { if (event.key === storageKey) { load(); persistAndRender(); } });
  window.addEventListener('online', updateOfflineState); window.addEventListener('offline', updateOfflineState);

  load(); updateCounters(); updateProductActions(); renderMiniCart();
  document.querySelectorAll('[data-commerce-page]').forEach(preparePage); updateOfflineState();
  if (!storageAvailable) toast('Local saving is unavailable in this browser session.');
}());
