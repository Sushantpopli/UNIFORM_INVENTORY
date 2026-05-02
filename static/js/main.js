/* ─── Cascading Dropdowns ───────────────────────────────────────────────────── */

function updateSelect(el, options, placeholder, disabled) {
  if (!el) return;
  el.innerHTML = '';
  if (placeholder) el.innerHTML += '<option value="">' + placeholder + '</option>';
  options.forEach(opt => { el.innerHTML += '<option value="' + opt.value + '">' + opt.text + '</option>'; });
  el.disabled = disabled;
  
  if (el.tomselect) {
    el.tomselect.clearOptions();
    el.tomselect.clear(true);
    if (placeholder) el.tomselect.addOption({value: '', text: placeholder});
    options.forEach(opt => el.tomselect.addOption({value: opt.value, text: opt.text}));
    if (disabled) el.tomselect.disable();
    else el.tomselect.enable();
  }
}

function setupCascadingDropdowns({ schoolSel, productSel, sizeSel, stockDisplay }) {
  const school = document.getElementById(schoolSel);
  const product = document.getElementById(productSel);
  const size = sizeSel ? document.getElementById(sizeSel) : null;
  const stockEl = stockDisplay ? document.getElementById(stockDisplay) : null;

  if (school) {
    school.addEventListener('change', async () => {
      const id = school.value;
      if (!id) { 
        updateSelect(product, [], '-- Select Product --', false);
        if (size) updateSelect(size, [], '-- Select Size --', false);
        if (stockEl) clearStock(stockEl);
        return; 
      }
      updateSelect(product, [], 'Loading...', true);
      if (size) updateSelect(size, [], '-- Select Size --', false);
      if (stockEl) clearStock(stockEl);
      
      const res = await fetch('/api/products-for-school/?school_id=' + id);
      const data = await res.json();
      const opts = data.map(p => ({value: p.id, text: p.name}));
      updateSelect(product, opts, '-- Select Product --', false);
    });
  }

  if (product) {
    product.addEventListener('change', async () => {
      const schoolId = school ? school.value : '';
      const productId = product.value;
      if (!productId || !schoolId) { 
        if (size) updateSelect(size, [], '-- Select Size --', false);
        if (stockEl) clearStock(stockEl);
        return; 
      }
      if (size) {
        updateSelect(size, [], 'Loading...', true);
        if (stockEl) clearStock(stockEl);
        
        const res = await fetch('/api/sizes-for-school-product/?school_id=' + schoolId + '&product_id=' + productId);
        const data = await res.json();
        const opts = data.map(s => ({value: s.id, text: s.size_value}));
        updateSelect(size, opts, '-- Select Size --', false);
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
    updateSelect(target, [], 'Loading...', true);
    const res = await fetch('/api/sizes-for-school-product/?school_id=' + school.value + '&product_id=' + product.value);
    const sizes = await res.json();
    const opts = sizes.map(s => ({value: s.id, text: s.size_value}));
    updateSelect(target, opts, '-- Select Size --', false);
  }

  if (school && product) {
    school.addEventListener('change', async () => {
      updateSelect(product, [], 'Loading...', true);
      const res = await fetch('/api/products-for-school/?school_id=' + school.value);
      const products = await res.json();
      const opts = products.map(p => ({value: p.id, text: p.name}));
      updateSelect(product, opts, '-- Select Product --', false);
      if (oldSize) updateSelect(oldSize, [], '-- Select Size --', false);
      if (newSize) updateSelect(newSize, [], '-- Select Size --', false);
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
