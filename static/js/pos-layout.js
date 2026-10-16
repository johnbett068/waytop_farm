// Measure the shell and workspace instead of guessing a header offset.
(() => {
  const workspace = document.querySelector('.pos-sales-workspace');
  const columns = workspace?.querySelector('.pos-columns');
  const header = document.querySelector('.staff-topbar');
  if (!columns || !header) return;

  const fitCheckout = () => {
    const gap = parseFloat(getComputedStyle(workspace).columnGap) || 0;
    // Sticky inset is a shell dimension, not the header's current screen position.
    // In particular, never carry a transient layout/scroll offset into the card.
    const headerStyle = getComputedStyle(header);
    const headerInset = parseFloat(headerStyle.top) || 0;
    const stickyTop = headerInset + header.offsetHeight;
    const workspaceTop = workspace.getBoundingClientRect().top + window.scrollY;
    const height = window.innerHeight - Math.max(stickyTop, workspaceTop) - gap;
    workspace.style.setProperty('--pos-sticky-top', `${stickyTop}px`);
    workspace.style.setProperty('--pos-checkout-height', `${Math.max(0, height)}px`);
  };
  const observer = new ResizeObserver(fitCheckout);
  observer.observe(header);
  observer.observe(workspace);
  window.addEventListener('resize', fitCheckout);
  fitCheckout();
})();
