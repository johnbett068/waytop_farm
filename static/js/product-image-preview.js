(() => {
  'use strict';
  document.querySelectorAll('[data-product-image-upload]').forEach((section) => {
  const input = section?.querySelector('input[type="file"]');
  const preview = section?.querySelector('[data-image-preview]');
  const details = section.querySelector('[data-image-details]');
  if (!input || !preview) return;
  let objectUrl;
  function clearPreview() {
    preview.hidden = true;
    preview.removeAttribute('src');
    details.hidden = true;
    details.textContent = '';
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = undefined;
  }
  input.addEventListener('change', () => {
    clearPreview();
    const file = input.files[0];
    if (!file) return;
    details.hidden = false;
    details.textContent = `Selected image: ${file.name} — ${(file.size / (1024 * 1024)).toFixed(2)} MiB (${file.size.toLocaleString()} bytes). Reading dimensions…`;
    objectUrl = URL.createObjectURL(file);
    preview.src = objectUrl;
    preview.hidden = false;
  });
  preview.addEventListener('load', () => {
    const file = input.files[0];
    if (!file || preview.getAttribute('src') !== objectUrl) return;
    const dimensions = `${preview.naturalWidth} × ${preview.naturalHeight} px`;
    const recommendation = preview.naturalWidth === 960 && preview.naturalHeight === 768
      ? 'Matches the recommended dimensions.'
      : 'Recommended: 960 × 768 px (5:4); other dimensions are allowed.';
    details.textContent = `Selected image: ${file.name} — ${dimensions} — ${(file.size / (1024 * 1024)).toFixed(2)} MiB (${file.size.toLocaleString()} bytes). ${recommendation} The file is validated when you save.`;
  });
  preview.addEventListener('error', () => {
    clearPreview();
    if (input.files[0]) {
      details.hidden = false;
      details.textContent = 'Preview unavailable. Choose a supported image; the file is validated when you save.';
    }
  });
  input.form.addEventListener('reset', clearPreview);
  window.addEventListener('pagehide', clearPreview);
  });
})();
