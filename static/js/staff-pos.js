(function () {
  'use strict';
  const page = document.querySelector('[data-pos-page]');
  if (!page) return;
  const fixtures = {
    jane: { name: 'Jane Atieno', role: 'Cashier', scope: 'Bomet Register BMT-01', capabilities: ['pos.view', 'pos.process_order', 'pos.process_sale'] },
    john: { name: 'John Bett', role: 'Operations Manager', scope: 'All locations', capabilities: ['pos.view', 'pos.process_order', 'pos.process_sale'] },
    amina: { name: 'Amina Noor', role: 'Administrator', scope: 'Administrative global scope', capabilities: [] }
  };
  const products = {
    hass: { name: 'Grafted Hass Avocado', unit: 'plant', price: 900 },
    tomato: { name: 'Anna F1 Tomato Seedling', unit: 'seedling', price: 200 },
    cabbage: { name: 'Gloria Star Cabbage', unit: 'seedling', price: 120 },
    media: { name: 'Premium Potting Media', unit: 'bag', price: 800 }
  };
  const storageKey = 'waytop.pos.authorization-simulation.v1';
  const select = page.querySelector('[data-pos-simulator-select]');
  const summary = page.querySelector('[data-pos-simulator-summary]');
  const live = page.querySelector('[data-pos-simulator-live]');
  const success = page.querySelector('[data-pos-success]');
  const permission = page.querySelector('[data-pos-permission]');
  const mode = page.dataset.stateMode;
  function setState(name) { ['loading', 'empty', 'error', 'permission', 'offline', 'success'].forEach(function (value) { const node = page.querySelector('[data-pos-' + value + ']'); if (node) node.hidden = value !== name; }); }
  function applyFixture(name, announce) {
    const fixture = fixtures[name] || fixtures.jane;
    const can = function (capability) { return fixture.capabilities.indexOf(capability) !== -1; };
    summary.textContent = fixture.name + ' · ' + fixture.role + ' · ' + fixture.scope;
    document.querySelectorAll('[data-pos-capability]').forEach(function (node) { node.hidden = !can(node.dataset.posCapability); });
    document.querySelectorAll('[data-module-capability="pos.view"]').forEach(function (node) { node.hidden = !can('pos.view'); });
    if (mode === 'success') { success.hidden = !can('pos.view'); permission.hidden = can('pos.view'); if (!can('pos.view') && announce) { const heading = permission.querySelector('h2'); heading.setAttribute('tabindex', '-1'); heading.focus(); } }
    if (announce) live.textContent = 'Simulation changed to ' + fixture.name + ', ' + fixture.role + '.';
    try { window.localStorage.setItem(storageKey, name); } catch (error) { /* optional */ }
  }
  setState(['loading', 'empty', 'error', 'permission', 'offline'].indexOf(mode) >= 0 ? mode : 'success');
  let selected = 'jane'; try { const stored = window.localStorage.getItem(storageKey); if (fixtures[stored]) selected = stored; } catch (error) { selected = 'jane'; }
  select.value = selected; applyFixture(selected, false); select.addEventListener('change', function () { applyFixture(select.value, true); });
  const retry = page.querySelector('[data-pos-retry]'); if (retry) retry.addEventListener('click', function () { window.location.href = window.location.pathname; });
  const toast = page.querySelector('[data-pos-toast]');
  function notify(message) { if (!toast) return; toast.textContent = message; toast.hidden = false; window.setTimeout(function () { toast.hidden = true; }, 3200); }
  document.querySelectorAll('[data-pos-placeholder]').forEach(function (button) { button.addEventListener('click', function () { notify(button.dataset.posPlaceholder); }); });
  const workspace = page.querySelector('[data-pos-sale-workspace]');
  if (!workspace) return;
  const lines = workspace.querySelector('[data-cart-lines]');
  function formatMoney(value) { return 'KSh ' + value.toLocaleString('en-KE'); }
  function updateTotals() {
    let subtotal = 0; let items = 0;
    lines.querySelectorAll('[data-cart-line]').forEach(function (line) { const quantity = Number(line.querySelector('[data-quantity]').textContent); const total = Number(line.dataset.price) * quantity; subtotal += total; items += quantity; line.querySelector('[data-line-total]').textContent = formatMoney(total); });
    workspace.querySelector('[data-cart-count]').textContent = items + (items === 1 ? ' item' : ' items');
    workspace.querySelector('[data-cart-subtotal]').textContent = formatMoney(subtotal);
    workspace.querySelector('[data-cart-total]').textContent = formatMoney(subtotal);
    workspace.querySelector('[data-complete-total]').textContent = formatMoney(subtotal);
  }
  function wireLine(line) {
    line.querySelector('[data-quantity-minus]').addEventListener('click', function () { const output = line.querySelector('[data-quantity]'); output.textContent = String(Math.max(1, Number(output.textContent) - 1)); updateTotals(); });
    line.querySelector('[data-quantity-plus]').addEventListener('click', function () { const output = line.querySelector('[data-quantity]'); output.textContent = String(Number(output.textContent) + 1); updateTotals(); });
    line.querySelector('[data-remove-line]').addEventListener('click', function () { line.remove(); updateTotals(); notify('Item removed from the local mock cart. No Inventory changed.'); });
  }
  lines.querySelectorAll('[data-cart-line]').forEach(wireLine);
  function createLine(code) {
    const product = products[code]; const line = document.createElement('article'); line.dataset.cartLine = code; line.dataset.price = String(product.price);
    const info = document.createElement('div'); const name = document.createElement('strong'); name.textContent = product.name; const unit = document.createElement('small'); unit.textContent = formatMoney(product.price) + ' · ' + product.unit; info.append(name, unit);
    const quantity = document.createElement('div'); quantity.className = 'quantity-control'; const minus = document.createElement('button'); minus.type = 'button'; minus.dataset.quantityMinus = ''; minus.textContent = '−'; minus.setAttribute('aria-label', 'Decrease ' + product.name + ' quantity'); const output = document.createElement('output'); output.dataset.quantity = ''; output.textContent = '1'; const plus = document.createElement('button'); plus.type = 'button'; plus.dataset.quantityPlus = ''; plus.textContent = '+'; plus.setAttribute('aria-label', 'Increase ' + product.name + ' quantity'); quantity.append(minus, output, plus);
    const total = document.createElement('strong'); total.dataset.lineTotal = ''; total.textContent = formatMoney(product.price); const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'cart-remove'; remove.dataset.removeLine = ''; remove.textContent = '×'; remove.setAttribute('aria-label', 'Remove ' + product.name);
    line.append(info, quantity, total, remove); wireLine(line); return line;
  }
  workspace.querySelectorAll('[data-add-product]').forEach(function (button) { button.addEventListener('click', function () { const code = button.dataset.addProduct; const existing = lines.querySelector('[data-cart-line="' + code + '"]'); if (existing) { const output = existing.querySelector('[data-quantity]'); output.textContent = String(Number(output.textContent) + 1); } else { lines.appendChild(createLine(code)); } updateTotals(); notify(products[code].name + ' added to the local mock cart.'); }); });
  const clear = workspace.querySelector('[data-clear-cart]'); if (clear) clear.addEventListener('click', function () { lines.replaceChildren(); updateTotals(); notify('Local mock cart cleared. No Order or Inventory record changed.'); });
  const complete = workspace.querySelector('[data-complete-sale]'); if (complete) complete.addEventListener('click', function () { notify('POS order preview only — no Order, payment, commitment or Inventory issue was created.'); });
  const search = workspace.querySelector('[data-pos-search]'); if (search) search.addEventListener('input', function () { const query = search.value.trim().toLowerCase(); workspace.querySelectorAll('[data-pos-product]').forEach(function (card) { card.hidden = query && card.dataset.name.toLowerCase().indexOf(query) === -1; }); });
  updateTotals();
}());
