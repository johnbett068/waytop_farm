const method = document.getElementById('pos-payment-method');
const reference = document.getElementById('pos-reference');
const field = document.getElementById('pos-reference-field');
const help = document.getElementById('pos-payment-help');
if (method && reference && field) {
  const complete = document.querySelector('[data-complete-sale]');
  const updatePayment = () => {
    const mpesa = method.value === 'MPESA';
    field.hidden = !mpesa;
    reference.required = mpesa;
    reference.disabled = !mpesa;
    if (help && help.dataset.mpesa) {
      help.textContent = mpesa ? help.dataset.mpesa : help.dataset.cash;
    }
    if (!mpesa) reference.value = '';
    if (complete) {
      complete.disabled = complete.dataset.cartValid !== 'true' || (mpesa && !reference.value.trim());
    }
  };
  method.addEventListener('change', updatePayment);
  reference.addEventListener('input', updatePayment);
  updatePayment();
}
