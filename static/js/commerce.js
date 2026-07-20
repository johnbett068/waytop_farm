(function () {
  'use strict';

  const catalogNode = document.getElementById('commerce-catalog-data');
  if (!catalogNode) return;

  const catalog = JSON.parse(catalogNode.textContent || '[]');
  const products = new Map(catalog.map(function (product) { return [product.slug, product]; }));
  const storageKey = 'waytop-commerce-v1';
  let state = { wishlist: [], cart: {} };
  let storageAvailable = true;
  let lastDrawerTrigger = null;

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, function (character) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character];
    });
  }

  function money(value) { return 'KES ' + Math.round(value).toLocaleString('en-KE'); }
  function productFor(slug) { return products.get(slug); }

  function sanitize(raw) {
    const clean = { wishlist: [], cart: {} };
    if (raw && Array.isArray(raw.wishlist)) {
      clean.wishlist = raw.wishlist.filter(function (slug, index, list) {
        return products.has(slug) && list.indexOf(slug) === index;
      });
    }
    if (raw && raw.cart && typeof raw.cart === 'object') {
      Object.keys(raw.cart).forEach(function (slug) {
        const product = productFor(slug);
        if (!product) return;
        const item = raw.cart[slug] || {};
        clean.cart[slug] = {
          quantity: Math.min(99, Math.max(1, parseInt(item.quantity, 10) || 1))
        };
      });
    }
    return clean;
  }

  function load() {
    try {
      state = sanitize(JSON.parse(window.localStorage.getItem(storageKey) || '{}'));
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
    return Object.keys(state.cart).map(function (slug) {
      return { product: productFor(slug), item: state.cart[slug] };
    }).filter(function (entry) { return entry.product; });
  }

  function cartQuantity() {
    return cartEntries().reduce(function (total, entry) { return total + entry.item.quantity; }, 0);
  }

  function cartTotal() {
    return cartEntries().reduce(function (total, entry) { return total + entry.product.price * entry.item.quantity; }, 0);
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
    document.querySelectorAll('[data-wishlist-count]').forEach(function (node) {
      node.textContent = wishlistCount; node.hidden = wishlistCount === 0;
      node.classList.remove('is-bumping'); void node.offsetWidth; node.classList.add('is-bumping');
    });
    document.querySelectorAll('[data-cart-count]').forEach(function (node) {
      node.textContent = cartCount; node.hidden = cartCount === 0;
      node.classList.remove('is-bumping'); void node.offsetWidth; node.classList.add('is-bumping');
    });
    document.querySelectorAll('[data-wishlist-link]').forEach(function (node) { node.setAttribute('aria-label', 'Wishlist, ' + wishlistCount + ' items'); });
    document.querySelectorAll('[data-cart-open]').forEach(function (node) { node.setAttribute('aria-label', 'Open cart, ' + cartCount + ' items'); });
  }

  function updateProductActions() {
    document.querySelectorAll('[data-wishlist-toggle]').forEach(function (button) {
      const slug = button.getAttribute('data-wishlist-toggle');
      const selected = state.wishlist.indexOf(slug) !== -1;
      const product = productFor(slug);
      button.setAttribute('aria-pressed', String(selected));
      button.setAttribute('aria-label', (selected ? 'Remove ' : 'Save ') + (product ? product.name : 'product') + (selected ? ' from wishlist' : ' to wishlist'));
      const symbol = button.querySelector('[aria-hidden="true"]');
      if (symbol) symbol.textContent = selected ? '♥' : '♡';
    });
  }

  function persistAndRender() {
    save(); updateCounters(); updateProductActions(); renderMiniCart(); renderWishlistPage(); renderCartPage();
  }

  function toggleWishlist(slug) {
    const product = productFor(slug); if (!product) return;
    const index = state.wishlist.indexOf(slug);
    if (index === -1) {
      state.wishlist.push(slug); persistAndRender(); toast(product.name + ' saved to your wishlist.');
    } else {
      state.wishlist.splice(index, 1); persistAndRender();
      toast(product.name + ' removed from your wishlist.', 'Undo', function () { if (state.wishlist.indexOf(slug) === -1) state.wishlist.push(slug); persistAndRender(); });
    }
  }

  function addToCart(slug, removeFromWishlist) {
    const product = productFor(slug); if (!product) return;
    if (product.stock === 'out-of-stock') { toast(product.name + ' is currently unavailable. Save it to your wishlist instead.'); return; }
    if (state.cart[slug]) state.cart[slug].quantity = Math.min(99, state.cart[slug].quantity + 1);
    else state.cart[slug] = { quantity: 1 };
    if (removeFromWishlist) state.wishlist = state.wishlist.filter(function (item) { return item !== slug; });
    persistAndRender(); toast(product.name + ' added to your cart.');
  }

  function removeCart(slug) {
    const product = productFor(slug); const previous = state.cart[slug]; if (!product || !previous) return;
    delete state.cart[slug]; persistAndRender();
    toast(product.name + ' removed from your cart.', 'Undo', function () { state.cart[slug] = previous; persistAndRender(); });
  }

  function miniCartMarkup(entry) {
    return '<article class="mini-cart-item">' +
      '<img src="' + escapeHtml(entry.product.image_url) + '" alt="">' +
      '<div><h3 class="heading-4"><a href="' + escapeHtml(entry.product.product_url) + '">' + escapeHtml(entry.product.name) + '</a></h3><p>' + entry.item.quantity + ' × ' + escapeHtml(entry.product.unit) + '</p><p class="mini-cart-item__price">' + money(entry.product.price * entry.item.quantity) + '</p></div>' +
      '<button class="commerce-icon-button" type="button" data-cart-remove="' + escapeHtml(entry.product.slug) + '" aria-label="Remove ' + escapeHtml(entry.product.name) + '"><span aria-hidden="true">×</span></button></article>';
  }

  function renderMiniCart() {
    const container = document.querySelector('[data-mini-cart-items]'); if (!container) return;
    const entries = cartEntries();
    container.innerHTML = entries.map(miniCartMarkup).join('');
    document.querySelector('[data-mini-cart-empty]').hidden = entries.length !== 0;
    document.querySelector('[data-mini-cart-footer]').hidden = entries.length === 0;
    const total = document.querySelector('[data-mini-cart-total]'); if (total) total.textContent = money(cartTotal());
  }

  function wishlistMarkup(product) {
    const unavailable = product.stock === 'out-of-stock';
    return '<article class="wishlist-card" data-commerce-product="' + escapeHtml(product.slug) + '">' +
      '<div class="wishlist-card__media"><a href="' + escapeHtml(product.product_url) + '"><img src="' + escapeHtml(product.image_url) + '" alt="' + escapeHtml(product.name + ' nursery seedlings') + '"></a><button class="commerce-heart" type="button" data-wishlist-toggle="' + escapeHtml(product.slug) + '" aria-pressed="true" aria-label="Remove ' + escapeHtml(product.name) + ' from wishlist"><span aria-hidden="true">♥</span></button></div>' +
      '<div class="wishlist-card__body"><p class="caption">' + escapeHtml(product.category) + '</p><h2 class="heading-3"><a href="' + escapeHtml(product.product_url) + '">' + escapeHtml(product.name) + '</a></h2><p class="wishlist-card__meta">' + escapeHtml(product.variety + ' · ' + product.stock_label) + '</p><p class="wishlist-card__price">' + money(product.price) + ' <span class="small">per ' + escapeHtml(product.unit) + '</span></p>' +
      (unavailable ? '<p class="commerce-unavailable">Currently unavailable. Keep this item saved for a future nursery batch.</p>' : '') +
      '<div class="wishlist-card__actions"><button class="btn btn--primary" type="button" data-wishlist-move="' + escapeHtml(product.slug) + '"' + (unavailable ? ' disabled aria-disabled="true"' : '') + '>Move to cart</button><a class="btn btn--outline" href="' + escapeHtml(product.product_url) + '">View details</a></div></div></article>';
  }

  function renderWishlistPage() {
    const page = document.querySelector('[data-commerce-page="wishlist"]'); if (!page || page.dataset.ready !== 'true') return;
    const grid = page.querySelector('[data-wishlist-grid]'); const empty = page.querySelector('[data-wishlist-empty]');
    const list = state.wishlist.map(productFor).filter(Boolean);
    grid.innerHTML = list.map(wishlistMarkup).join(''); grid.hidden = list.length === 0; empty.hidden = list.length !== 0;
    page.querySelector('[data-clear-wishlist]').hidden = list.length === 0; updateProductActions();
  }

  function cartMarkup(entry) {
    const product = entry.product; const item = entry.item; const unavailable = product.stock === 'out-of-stock';
    return '<article class="cart-item" data-cart-item="' + escapeHtml(product.slug) + '"><img class="cart-item__media" src="' + escapeHtml(product.image_url) + '" alt="' + escapeHtml(product.name + ' nursery seedlings') + '"><div class="cart-item__content">' +
      '<div class="cart-item__top"><div><p class="caption">' + escapeHtml(product.category) + '</p><h2 class="heading-3"><a href="' + escapeHtml(product.product_url) + '">' + escapeHtml(product.name) + '</a></h2><p class="cart-item__unit">' + money(product.price) + ' per ' + escapeHtml(product.unit) + '</p></div><button class="commerce-text-button" type="button" data-cart-remove="' + escapeHtml(product.slug) + '">Remove</button></div>' +
      (unavailable ? '<p class="commerce-unavailable">This product is currently unavailable and cannot proceed to checkout.</p>' : '') +
      '<div class="cart-item__controls"><label class="commerce-field"><span>Quantity</span><span class="quantity-control"><button type="button" data-quantity-action="decrease" aria-label="Decrease ' + escapeHtml(product.name) + ' quantity">−</button><input type="number" min="1" max="99" value="' + item.quantity + '" data-cart-quantity aria-label="Quantity for ' + escapeHtml(product.name) + '"><button type="button" data-quantity-action="increase" aria-label="Increase ' + escapeHtml(product.name) + ' quantity">+</button></span></label></div>' +
      '<div class="cart-item__footer"><span class="small">' + escapeHtml(product.stock_label) + '</span><strong class="cart-item__line-total">' + money(product.price * item.quantity) + '</strong></div></div></article>';
  }

  function renderCartPage() {
    const page = document.querySelector('[data-commerce-page="cart"]'); if (!page || page.dataset.ready !== 'true') return;
    const entries = cartEntries(); const items = page.querySelector('[data-cart-items]');
    items.innerHTML = entries.map(cartMarkup).join('');
    page.querySelector('[data-cart-layout]').hidden = entries.length === 0; page.querySelector('[data-cart-empty]').hidden = entries.length !== 0; page.querySelector('[data-clear-cart]').hidden = entries.length === 0;
    const count = cartQuantity(); page.querySelector('[data-summary-items]').textContent = count + (count === 1 ? ' item' : ' items');
    page.querySelector('[data-summary-subtotal]').textContent = money(cartTotal()); page.querySelector('[data-summary-total]').textContent = money(cartTotal());
  }

  function preparePage(page) {
    const loading = page.querySelector('[data-commerce-loading]'); const error = page.querySelector('[data-commerce-error]');
    const mode = page.dataset.stateMode;
    if (mode === 'loading') return;
    window.setTimeout(function () {
      loading.hidden = true;
      if (mode === 'error') { error.hidden = false; return; }
      page.dataset.ready = 'true'; renderWishlistPage(); renderCartPage();
    }, 220);
  }

  function updateOfflineState() {
    document.querySelectorAll('[data-commerce-page]').forEach(function (page) {
      let note = page.querySelector('.commerce-offline-note');
      if (!navigator.onLine && !note) {
        note = document.createElement('div'); note.className = 'commerce-offline-note'; note.innerHTML = '<strong>Offline</strong><span>Your local wishlist and cart remain available. Product availability cannot be refreshed.</span>';
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
    const add = event.target.closest('[data-cart-add]'); if (add && !add.disabled) { addToCart(add.dataset.cartAdd, false); return; }
    const move = event.target.closest('[data-wishlist-move]'); if (move && !move.disabled) { addToCart(move.dataset.wishlistMove, true); return; }
    const remove = event.target.closest('[data-cart-remove]'); if (remove) { removeCart(remove.dataset.cartRemove); return; }
    const open = event.target.closest('[data-cart-open]'); if (open) { openCart(open); return; }
    if (event.target.closest('[data-cart-close]')) { closeCart(); return; }
    const quantityAction = event.target.closest('[data-quantity-action]');
    if (quantityAction) {
      const row = quantityAction.closest('[data-cart-item]'); const slug = row.dataset.cartItem; const delta = quantityAction.dataset.quantityAction === 'increase' ? 1 : -1;
      state.cart[slug].quantity = Math.min(99, Math.max(1, state.cart[slug].quantity + delta)); persistAndRender(); return;
    }
    if (event.target.closest('[data-clear-wishlist]')) { const previous = state.wishlist.slice(); state.wishlist = []; persistAndRender(); toast('Wishlist cleared.', 'Undo', function () { state.wishlist = previous; persistAndRender(); }); return; }
    if (event.target.closest('[data-clear-cart]')) { const previous = Object.assign({}, state.cart); state.cart = {}; persistAndRender(); toast('Cart cleared.', 'Undo', function () { state.cart = previous; persistAndRender(); }); return; }
    if (event.target.closest('[data-commerce-retry]')) { const url = new URL(window.location.href); url.searchParams.delete('state'); window.location.href = url.toString(); return; }
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

  window.addEventListener('storage', function (event) {
    if (event.key !== storageKey) return;
    load(); updateCounters(); updateProductActions(); renderMiniCart(); renderWishlistPage(); renderCartPage();
  });
  window.addEventListener('online', updateOfflineState); window.addEventListener('offline', updateOfflineState);

  load(); updateCounters(); updateProductActions(); renderMiniCart();
  document.querySelectorAll('[data-commerce-page]').forEach(preparePage); updateOfflineState();
  if (!storageAvailable) toast('Local saving is unavailable in this browser session.');
}());
