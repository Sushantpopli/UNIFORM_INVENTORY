/* ─── Cascading Dropdowns ───────────────────────────────────────────────────── */

function setupCascadingDropdowns({ schoolSel, productSel, sizeSel, stockDisplay }) {
  const school = document.getElementById(schoolSel);
  const product = document.getElementById(productSel);
  const size = sizeSel ? document.getElementById(sizeSel) : null;
  const stockEl = stockDisplay ? document.getElementById(stockDisplay) : null;

  function setLoading(el) { el.innerHTML = '<option value="">Loading...</option>'; el.disabled = true; }
  function setPlaceholder(el, text) { el.innerHTML = '<option value="">' + text + '</option>'; el.disabled = false; }

  if (school) {
    school.addEventListener('change', async () => {
      const id = school.value;
      if (!id) { setPlaceholder(product, '-- Select Product --'); if (size) setPlaceholder(size, '-- Select Size --'); if (stockEl) clearStock(stockEl); return; }
      setLoading(product);
      if (size) setPlaceholder(size, '-- Select Size --');
      if (stockEl) clearStock(stockEl);
      const res = await fetch('/api/products-for-school/?school_id=' + id);
      const data = await res.json();
      product.innerHTML = '<option value="">-- Select Product --</option>';
      data.forEach(p => { product.innerHTML += '<option value="' + p.id + '">' + p.name + '</option>'; });
      product.disabled = false;
    });
  }

  if (product) {
    product.addEventListener('change', async () => {
      const schoolId = school ? school.value : '';
      const productId = product.value;
      if (!productId || !schoolId) { if (size) setPlaceholder(size, '-- Select Size --'); if (stockEl) clearStock(stockEl); return; }
      if (size) {
        setLoading(size);
        if (stockEl) clearStock(stockEl);
        const res = await fetch('/api/sizes-for-school-product/?school_id=' + schoolId + '&product_id=' + productId);
        const data = await res.json();
        size.innerHTML = '<option value="">-- Select Size --</option>';
        data.forEach(s => { size.innerHTML += '<option value="' + s.id + '">' + s.size_value + '</option>'; });
        size.disabled = false;
      }
    });
  }

  if (size && stockEl) {
    size.addEventListener('change', async () => {
      const schoolId = school ? school.value : '';
      const productId = product ? product.value : '';
      const sizeId = size.value;
      if (!sizeId || !schoolId || !productId) { clearStock(stockEl); return; }
      stockEl.innerHTML = '<span class="spinner"></span>';
      const res = await fetch('/api/stock-check/?school_id=' + schoolId + '&product_id=' + productId + '&size_id=' + sizeId);
      const data = await res.json();
      renderStock(stockEl, data.stock, data.threshold);
    });
  }
}

function clearStock(el) {
  el.innerHTML = '<span style="color:var(--text-muted)">Select school, product & size above</span>';
  el.classList.remove('loaded');
}

function renderStock(el, stock, threshold) {
  el.classList.add('loaded');
  var cls = 'ok', label = 'In Stock';
  if (stock === 0) { cls = 'out'; label = 'OUT OF STOCK'; }
  else if (stock <= threshold) { cls = 'low'; label = 'Low Stock'; }
  el.innerHTML = '<span class="stock-num ' + cls + '">' + stock + '</span><div><div style="font-weight:700;font-size:0.88rem">' + label + '</div><div class="stock-label">units available</div></div>';
}


/* ─── Lookup (Dashboard) ───────────────────────────────────────────────────── */

function setupLookup() {
  setupCascadingDropdowns({
    schoolSel: 'lookup-school',
    productSel: 'lookup-product',
    sizeSel: 'lookup-size',
    stockDisplay: 'lookup-result',
  });
}


/* ─── Exchange: two size pickers ────────────────────────────────────────────── */

function setupExchangeDropdowns() {
  const school = document.getElementById('school');
  const product = document.getElementById('product');
  const oldSize = document.getElementById('old_size');
  const newSize = document.getElementById('new_size');

  async function loadSizes(target) {
    if (!school.value || !product.value) return;
    target.innerHTML = '<option value="">Loading...</option>';
    target.disabled = true;
    const res = await fetch('/api/sizes-for-school-product/?school_id=' + school.value + '&product_id=' + product.value);
    const sizes = await res.json();
    target.innerHTML = '<option value="">-- Select Size --</option>';
    sizes.forEach(s => { target.innerHTML += '<option value="' + s.id + '">' + s.size_value + '</option>'; });
    target.disabled = false;
  }

  if (school && product) {
    school.addEventListener('change', async () => {
      product.innerHTML = '<option value="">Loading...</option>';
      product.disabled = true;
      const res = await fetch('/api/products-for-school/?school_id=' + school.value);
      const products = await res.json();
      product.innerHTML = '<option value="">-- Select Product --</option>';
      products.forEach(p => { product.innerHTML += '<option value="' + p.id + '">' + p.name + '</option>'; });
      product.disabled = false;
      if (oldSize) oldSize.innerHTML = '<option value="">-- Select Size --</option>';
      if (newSize) newSize.innerHTML = '<option value="">-- Select Size --</option>';
    });
    product.addEventListener('change', () => {
      if (oldSize) loadSizes(oldSize);
      if (newSize) loadSizes(newSize);
    });
  }
}


/* ─── Confirmation Dialog ───────────────────────────────────────────────────── */

function confirmAction(form, message) {
  // Prevent double submit
  if (form.dataset.submitting === 'true') return false;

  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML =
    '<div class="modal-box">' +
      '<div class="modal-title">Please Confirm</div>' +
      '<div class="modal-text">' + message + '</div>' +
      '<div class="modal-actions">' +
        '<button class="btn btn-outline" id="modal-cancel">Go Back</button>' +
        '<button class="btn btn-primary" id="modal-confirm">Yes, Continue</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(overlay);

  document.getElementById('modal-cancel').addEventListener('click', function() {
    overlay.remove();
  });
  document.getElementById('modal-confirm').addEventListener('click', function() {
    form.dataset.submitting = 'true';
    overlay.remove();
    form.submit();
  });

  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) overlay.remove();
  });

  return false;
}


/* ─── Auto-dismiss alerts ───────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.alert').forEach(function(el) {
    setTimeout(function() {
      el.style.transition = 'opacity 0.5s, transform 0.5s';
      el.style.opacity = '0';
      el.style.transform = 'translateX(-20px)';
      setTimeout(function() { el.remove(); }, 500);
    }, 5000);
  });

  // Auto-focus first select on form pages
  var firstSelect = document.querySelector('.form-card select, .lookup-card select');
  if (firstSelect) firstSelect.focus();
});
