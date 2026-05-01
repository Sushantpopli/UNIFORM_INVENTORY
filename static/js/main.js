/* ─── Cascading Dropdown Logic ──────────────────────────────────────────────── */

function setupCascadingDropdowns({ schoolSel, productSel, sizeSel, stockDisplay }) {
  const school = document.getElementById(schoolSel);
  const product = document.getElementById(productSel);
  const size = sizeSel ? document.getElementById(sizeSel) : null;
  const stockEl = stockDisplay ? document.getElementById(stockDisplay) : null;

  function setLoading(el) {
    el.innerHTML = '<option value="">Loading...</option>';
    el.disabled = true;
  }
  function setPlaceholder(el, text) {
    el.innerHTML = `<option value="">${text}</option>`;
    el.disabled = false;
  }

  if (school) {
    school.addEventListener('change', async () => {
      const schoolId = school.value;
      if (!schoolId) {
        setPlaceholder(product, '— Select Product —');
        if (size) setPlaceholder(size, '— Select Size —');
        if (stockEl) clearStock(stockEl);
        return;
      }
      setLoading(product);
      if (size) setPlaceholder(size, '— Select Size —');
      if (stockEl) clearStock(stockEl);

      const res = await fetch(`/api/products-for-school/?school_id=${schoolId}`);
      const products = await res.json();
      product.innerHTML = '<option value="">— Select Product —</option>';
      products.forEach(p => {
        product.innerHTML += `<option value="${p.id}">${p.name}</option>`;
      });
      product.disabled = false;
    });
  }

  if (product) {
    product.addEventListener('change', async () => {
      const schoolId = school ? school.value : '';
      const productId = product.value;
      if (!productId || !schoolId) {
        if (size) setPlaceholder(size, '— Select Size —');
        if (stockEl) clearStock(stockEl);
        return;
      }
      if (size) {
        setLoading(size);
        if (stockEl) clearStock(stockEl);
        const res = await fetch(`/api/sizes-for-school-product/?school_id=${schoolId}&product_id=${productId}`);
        const sizes = await res.json();
        size.innerHTML = '<option value="">— Select Size —</option>';
        sizes.forEach(s => {
          size.innerHTML += `<option value="${s.id}">${s.size_value}</option>`;
        });
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
      const res = await fetch(`/api/stock-check/?school_id=${schoolId}&product_id=${productId}&size_id=${sizeId}`);
      const data = await res.json();
      renderStock(stockEl, data.stock, data.threshold);
    });
  }
}

function clearStock(el) {
  el.innerHTML = '<span style="color:var(--text-muted)">— select school, product & size —</span>';
  el.classList.remove('loaded');
}

function renderStock(el, stock, threshold) {
  el.classList.add('loaded');
  let cls = 'ok', label = 'In Stock';
  if (stock === 0) { cls = 'out'; label = 'OUT OF STOCK'; }
  else if (stock <= threshold) { cls = 'low'; label = 'Low Stock'; }
  el.innerHTML = `Current Stock: <span class="val ${cls}">${stock}</span> &nbsp;<span class="text-muted">(${label})</span>`;
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
    const res = await fetch(`/api/sizes-for-school-product/?school_id=${school.value}&product_id=${product.value}`);
    const sizes = await res.json();
    target.innerHTML = '<option value="">— Select Size —</option>';
    sizes.forEach(s => { target.innerHTML += `<option value="${s.id}">${s.size_value}</option>`; });
    target.disabled = false;
  }

  if (school && product) {
    school.addEventListener('change', async () => {
      product.innerHTML = '<option value="">Loading...</option>';
      product.disabled = true;
      const res = await fetch(`/api/products-for-school/?school_id=${school.value}`);
      const products = await res.json();
      product.innerHTML = '<option value="">— Select Product —</option>';
      products.forEach(p => { product.innerHTML += `<option value="${p.id}">${p.name}</option>`; });
      product.disabled = false;
      if (oldSize) oldSize.innerHTML = '<option value="">— Select Size —</option>';
      if (newSize) newSize.innerHTML = '<option value="">— Select Size —</option>';
    });
    product.addEventListener('change', () => {
      if (oldSize) loadSizes(oldSize);
      if (newSize) loadSizes(newSize);
    });
  }
}

/* ─── Auto-dismiss messages ─────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.5s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 500);
    }, 4000);
  });
});
