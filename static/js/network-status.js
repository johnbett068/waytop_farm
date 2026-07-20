(function () {
  'use strict';

  const banner = document.getElementById('offline-banner');
  if (!banner) return;

  const updateStatus = function () {
    banner.hidden = navigator.onLine;
  };

  window.addEventListener('online', updateStatus);
  window.addEventListener('offline', updateStatus);
  updateStatus();
}());
