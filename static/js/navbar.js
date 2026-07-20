document.addEventListener('DOMContentLoaded', function () {
  const navbar = document.getElementById('site-navbar');
  const drawer = document.getElementById('nav-drawer');
  const toggles = document.querySelectorAll('.nav-bar__toggle');
  const closeTriggers = document.querySelectorAll('[data-nav-close="true"]');
  const panel = drawer ? drawer.querySelector('.nav-drawer__panel') : null;
  let previouslyFocused = null;

  if (!navbar || !drawer) {
    return;
  }

  const setScrolled = function () {
    if (window.scrollY > 60) {
      navbar.classList.add('is-scrolled');
    } else {
      navbar.classList.remove('is-scrolled');
    }
  };

  setScrolled();
  window.addEventListener('scroll', setScrolled, { passive: true });

  const openDrawer = function () {
    previouslyFocused = document.activeElement;
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    toggles.forEach(function (toggle) { toggle.setAttribute('aria-expanded', 'true'); });
    document.body.style.overflow = 'hidden';
    if (panel) panel.focus();
  };

  const closeDrawer = function () {
    drawer.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    toggles.forEach(function (toggle) { toggle.setAttribute('aria-expanded', 'false'); });
    document.body.style.overflow = '';
    if (previouslyFocused) previouslyFocused.focus();
  };

  toggles.forEach(function (toggle) {
    toggle.addEventListener('click', function () {
      if (drawer.classList.contains('is-open')) {
        closeDrawer();
      } else {
        openDrawer();
      }
    });
  });

  closeTriggers.forEach(function (trigger) {
    trigger.addEventListener('click', closeDrawer);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      closeDrawer();
    }

    if (event.key === 'Tab' && drawer.classList.contains('is-open') && panel) {
      const focusable = panel.querySelectorAll('a[href], button:not([disabled]), [tabindex="0"]');
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    }
  });

  drawer.querySelectorAll('a').forEach(function (link) {
    link.addEventListener('click', closeDrawer);
  });
});
