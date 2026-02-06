from __future__ import annotations

HTML_TEMPLATE = """
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Available Medical Cannabis</title>
<style>
:root {
  --bg: #0f1115;
  --fg: #e8e8e8;
  --panel: #1c1f26;
  --border: #2b3040;
  --accent: #7cc7ff;
  --pill: #242a35;
  --hover: #2f3542;
  --muted: #aab2c0;
}
.light {
  --bg: #f6f7fb;
  --fg: #111;
  --panel: #ffffff;
  --border: #d5d8e0;
  --accent: #2f6fed;
  --pill: #e9ecf3;
  --hover: #dde3ef;
  --muted: #555;
}
body{background:var(--bg);color:var(--fg);font-family:Arial;padding:16px;margin:0;transition:background .2s ease,color .2s ease}
.export-header{display:flex;align-items:flex-start;justify-content:flex-start;gap:12px;margin-bottom:8px}
.export-header h1{margin:0 0 4px 0}
.export-pill{padding:6px 10px;border-radius:999px;border:1px solid var(--border);background:var(--panel);color:var(--muted);font-size:12px;white-space:nowrap}
.controls{display:flex;gap:8px;align-items:center;margin-bottom:16px;flex-wrap:wrap}
.controls-inner{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.controls-right{margin-left:auto;display:flex;gap:8px;align-items:center}
.basket-summary{padding:6px 10px;border-radius:10px;border:1px solid var(--border);background:var(--panel);color:var(--fg);font-weight:700;min-width:180px;text-align:center}
.btn-basket{padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:var(--panel);color:var(--accent);font-weight:700;cursor:pointer}
.btn-basket:hover{background:var(--hover)}
.btn-basket.added{background:var(--accent);color:var(--bg);border-color:var(--accent)}
.btn-basket.added:hover{background:var(--accent);color:var(--bg)}
.basket-button{padding:8px 12px;border-radius:10px;border:1px solid var(--border);background:var(--panel);color:var(--accent);font-weight:700;cursor:pointer;display:flex;gap:6px;align-items:center}
.basket-button:hover{background:var(--hover)}
.basket-button.active{background:var(--accent);color:var(--bg);border-color:var(--accent)}
.basket-modal{position:fixed;inset:0;background:rgba(0,0,0,0.6);display:none;align-items:center;justify-content:center;z-index:9999}
.image-modal{position:fixed;inset:0;background:rgba(0,0,0,0.75);display:none;align-items:center;justify-content:center;z-index:10000}
.image-modal img{max-width:90vw;max-height:85vh;border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,0.5)}
.type-badge{cursor:pointer}
.basket-panel{background:var(--panel);color:var(--fg);border:1px solid var(--border);border-radius:12px;min-width:320px;max-width:520px;max-height:70vh;overflow:auto;padding:16px;box-shadow:0 10px 30px rgba(0,0,0,0.3)}
.basket-row{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)}
.basket-row:last-child{border-bottom:none}
.basket-title{font-weight:700;font-size:16px;margin-bottom:8px}
.basket-empty{padding:8px 0;color:var(--muted)}
.basket-qty{width:64px}
.type-badge{position:absolute;top:32px;right:8px;width:60px;height:60px;object-fit:contain;opacity:0.95}
.badge-new{position:absolute;top:6px;right:6px;left:auto;display:inline-block;padding:2px 8px;border-radius:999px;background:var(--accent);color:var(--bg);font-size:11px;font-weight:700;white-space:nowrap;max-width:120px;overflow:hidden;text-overflow:ellipsis}
.badge-removed{position:absolute;top:6px;right:6px;left:auto;display:inline-block;padding:2px 8px;border-radius:999px;background:#c0392b;color:#fff;font-size:11px;font-weight:700;white-space:nowrap;max-width:120px;overflow:hidden;text-overflow:ellipsis}
.range-group{display:flex;flex-direction:column;gap:4px;margin:4px 0}
.range-line{display:flex;align-items:center;gap:3px;min-width:140px;position:relative;padding-top:14px;padding-bottom:6px}
.range-slider{position:relative;flex:1;min-width:120px;height:36px}
.range-slider::before{content:"";position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);height:6px;background:var(--border);border-radius:999px;z-index:1}
.range-slider input[type=range]{position:absolute;left:0;right:0;top:50%;transform:translateY(-54%);height:36px;width:100%;margin:0;background:transparent;pointer-events:none;-webkit-appearance:none;appearance:none;z-index:5}
.range-slider input.range-max{z-index:6}
.range-slider input.range-min{z-index:7}
.range-slider input[type=range]::-webkit-slider-thumb{pointer-events:auto;position:relative;z-index:10;margin-top:-6px}
.range-slider input[type=range]::-moz-range-thumb{pointer-events:auto;position:relative;z-index:10;top:-4px}
.range-slider input[type=range]::-webkit-slider-runnable-track{height:6px;background:transparent;border-radius:999px}
.range-slider input[type=range]::-moz-range-track{height:6px;background:transparent;border-radius:999px}
.range-label{font-size:12px;color:var(--muted)}
.range-values{font-size:14px;font-weight:700;color:var(--fg);text-align:center}
.range-tag{font-size:12px;color:var(--muted);min-width:28px;text-align:center}
.range-val{font-size:12px;color:var(--fg);min-width:48px;text-align:center}
.range-title{position:absolute;left:50%;top:6px;transform:translate(-50%,-50%);font-size:12px;color:var(--muted);pointer-events:none}
input.search-box{padding:8px 10px;border-radius:10px;border:1px solid var(--border);background:var(--panel);color:var(--fg);min-width:200px}
button{padding:8px 10px;border-radius:8px;border:1px solid var(--border);background:var(--panel);color:var(--accent);font-weight:600;cursor:pointer;transition:background .2s ease,color .2s ease}
button.btn-filter{background:var(--panel);color:var(--accent)}
button.btn-filter.active{background:var(--accent);color:var(--bg);background-image:none}
button:hover{background:var(--hover)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}
.card{background:var(--panel);padding:12px;border-radius:12px;border:1px solid var(--border);position:relative;display:flex;flex-direction:column;min-height:300px;content-visibility:auto;contain-intrinsic-size:320px 320px}
.card-new{background:#0f2616;border-color:#1f5d35}
.card-removed{background:#2b1313;border-color:#6a1f1f}
.card-out{background:#2a0f10;border-color:#7a2626}
.card-restock{background:#0f2b19;border-color:#1f6a3a}
.light .card-out{background:#ffe2e2;border-color:#e6b0b0}
.light .card-restock{background:#e6ffef;border-color:#b3e0c5}
.card-fav{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.light .card-removed{background:#ffe6e6;border-color:#e0b3b3}
.light .card-new{background:#e6ffef;border-color:#b3e0c5}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;background:var(--pill);margin:4px 6px 0 0;font-size:13px;color:var(--fg)}
.pill.stock-up{background:#15331e;color:#b7f0c8}
.pill.stock-down{background:#3a1a1a;color:#f6c6c6}
.pill.stock-change{background:#2c2a12;color:#f7e4a1}
.light .pill.stock-up{background:#dff5e6;color:#116a2b}
.light .pill.stock-down{background:#ffdede;color:#b20000}
.light .pill.stock-change{background:#fff2cc;color:#7a5a00}
.flag-icon{width:18px;height:12px;object-fit:cover;border-radius:2px;margin-right:6px;vertical-align:-2px}
.pill-flag{font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',sans-serif}
.price-up{background:#3a1a1a;color:#f6c6c6}
.price-down{background:#15331e;color:#b7f0c8}
.light .price-up{background:#ffdede;color:#b20000}
.light .price-down{background:#dff5e6;color:#116a2b}
.card-price-up{border-color:#a13535;box-shadow:0 0 0 1px #a13535 inset}
.card-price-down{border-color:#2f7a46;box-shadow:0 0 0 1px #2f7a46 inset}
.card-content{display:flex;flex-direction:column;gap:6px;margin-top:auto}
.card-title{display:block;margin:4px 0 6px 0;padding-right:32px;overflow-wrap:break-word;word-wrap:break-word}
.brand-line{display:block;margin:2px 0;padding-right:32px;overflow-wrap:break-word;word-wrap:break-word}
.badge-price-up{display:inline-block;position:relative;top:0;left:0;padding:2px 8px;border-radius:999px;background:#3a1a1a;color:#f6c6c6;font-size:11px;font-weight:700;margin-right:6px}
.badge-price-down{display:inline-block;position:relative;top:0;left:0;padding:2px 8px;border-radius:999px;background:#15331e;color:#b7f0c8;font-size:11px;font-weight:700;margin-right:6px}
.light .badge-price-up{background:#ffdede;color:#b20000}
.light .badge-price-down{background:#dff5e6;color:#116a2b}
.card-actions{margin-top:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.search{display:inline-flex;align-items:center;justify-content:center;padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:var(--panel);color:var(--accent);text-decoration:none;font-weight:700;min-width:140px}
.search:hover{background:var(--panel);color:var(--accent)}
.small{font-size:13px;opacity:.85;color:var(--muted)}
.brand-filter{position:relative}
.brand-menu{position:absolute;top:110%;left:0;min-width:220px;max-height:260px;overflow:auto;display:none;z-index:999;background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:8px;box-shadow:0 8px 18px rgba(0,0,0,0.25)}
.brand-menu.open{display:block}
.brand-item{display:flex;align-items:center;gap:8px;padding:4px 6px;border-radius:8px}
.brand-item:hover{background:var(--hover)}
.brand-item input{accent-color:var(--accent)}
.load-more{display:flex;align-items:center;justify-content:center;gap:12px;margin:18px 0}
.stock-indicator{display:inline-block;width:14px;height:14px;min-width:14px;flex:0 0 14px;border-radius:50%;margin-right:10px;vertical-align:middle}
.stock-in{background:#2ecc71}
.stock-low{background:#f5a623}
.stock-out{background:#e74c3c}
.stock-not-prescribable{background:#999}
.strain-badge{position:absolute;top:32px;right:8px;width:60px;height:60px;object-fit:contain;opacity:0.95}
.card.has-type-icon .strain-badge{right:72px}
.fav-btn{position:absolute;bottom:10px;right:10px;border:none;background:transparent;color:var(--muted);font-size:30px;cursor:pointer;line-height:1}
.fav-btn.fav-on{color:var(--accent)}
.fav-btn:hover{background:transparent;color:inherit}
.badge-new{position:absolute;top:6px;right:6px;padding:2px 8px;border-radius:999px;background:var(--accent);color:var(--bg);font-size:11px;font-weight:700}
.badge-removed{position:absolute;top:6px;right:6px;padding:2px 8px;border-radius:999px;background:#c0392b;color:#fff;font-size:11px;font-weight:700}
h3.card-title{margin-right:48px;}
</style>
<script>
const state = { key: 'price', asc: false };
function updateSortButtons() {
    document.querySelectorAll('.sort-btn').forEach(btn => {
        const k = btn.dataset.sort;
        if (k === state.key) {
            const arrow = state.asc ? "↑" : "↓";
            btn.textContent = `${k.toUpperCase()} ${arrow}`;
            btn.classList.add('active');
        } else {
            btn.textContent = `${k.toUpperCase()}`;
            btn.classList.remove('active');
        }
    });
}
function sortCards(key, btn) {
    if (key === undefined || key === null) key = state.key || 'price';
    const grid = document.getElementById("grid");
    const cards = Array.from(grid.children);
    if (state.key === key) {
        state.asc = !state.asc;
    } else {
        state.key = key;
        state.asc = true;
    }
    const dir = state.asc ? 1 : -1;
    cards.sort((a, b) => {
        const avRaw = parseFloat(a.dataset[key]);
        const bvRaw = parseFloat(b.dataset[key]);
        const av = Number.isFinite(avRaw) ? avRaw : (key === 'price' ? Number.POSITIVE_INFINITY : 0);
        const bv = Number.isFinite(bvRaw) ? bvRaw : (key === 'price' ? Number.POSITIVE_INFINITY : 0);
        return (av - bv) * dir;
    });
    cards.forEach(c => grid.appendChild(c));
    updateSortButtons();
    applyVisibleLimit();
}
let activeTypes = new Set(['flower','oil','vape']);
let activeStrains = new Set(['Indica','Sativa','Hybrid']);
let favoritesOnly = false;
let showSmalls = true;
let showOutOfStock = false;
let brandFilter = new Set();
let searchTerm = "";
const VISIBLE_STEP = 30;
let visibleLimit = VISIBLE_STEP;
let filteredCards = [];
const priceMinBound = {price_min_bound};
const priceMaxBound = {price_max_bound};
let priceMinSel = priceMinBound;
let priceMaxSel = priceMaxBound;
const thcMinBound = {thc_min_bound};
const thcMaxBound = {thc_max_bound};
let thcMinSel = thcMinBound;
let thcMaxSel = thcMaxBound;
function applyVisibleLimit() {
    let shown = 0;
    filteredCards.forEach(c => {
        if (shown < visibleLimit) {
            c.style.display = '';
            shown += 1;
        } else {
            c.style.display = 'none';
        }
    });
    const btn = document.getElementById('loadMore');
    if (btn) btn.style.display = filteredCards.length > visibleLimit ? '' : 'none';
    const count = document.getElementById('visibleCount');
    if (count) {
        const total = filteredCards.length;
        count.textContent = total ? `${Math.min(visibleLimit, total)} / ${total}` : '';
    }
}
function applyFilters(resetLimit = true) {
    const grid = document.getElementById('grid');
    const cards = Array.from(grid.children);
    const term = searchTerm.trim().toLowerCase();
    if (resetLimit) visibleLimit = VISIBLE_STEP;
    filteredCards = [];
    cards.forEach(c => {
        const pt = (c.dataset.pt || '').toLowerCase();
        const isRemoved = c.dataset.removed === '1';
        const st = c.dataset.strainType || '';
        const favKey = c.dataset.favkey || '';
        const isSmalls = c.dataset.smalls === '1';
        const priceVal = parseFloat(c.dataset.price);
        const thcVal = parseFloat(c.dataset.thc);
        const priceOk = Number.isFinite(priceVal) ? (priceVal >= priceMinSel && priceVal <= priceMaxSel) : true;
        const thcOk = (pt === 'vape' || pt === 'oil' || pt === 'device') ? true : (Number.isFinite(thcVal) ? (thcVal >= thcMinSel && thcVal <= thcMaxSel) : true);
        const showType = isRemoved ? true : activeTypes.has(pt);
        const showStrain = (!st) ? true : activeStrains.has(st);
        const text = (c.dataset.strain || '') + ' ' + (c.dataset.brand || '') + ' ' + (c.dataset.producer || '') + ' ' + (c.dataset.productId || '');
        const matchesSearch = term ? text.toLowerCase().includes(term) : true;
        const brandText = (c.dataset.brand || '').trim();
        const brandOk = brandFilter.size > 0 ? brandFilter.has(brandText) : true;
        const favOk = favoritesOnly ? favorites.has(favKey) : true;
        const isOut = c.dataset.out === '1';
        const stockOk = showOutOfStock || !isOut;
        const smallsOk = showSmalls || !isSmalls;
        if (showType && showStrain && matchesSearch && brandOk && priceOk && thcOk && favOk && smallsOk && stockOk) {
            filteredCards.push(c);
        }
        c.style.display = 'none';
    });
    applyVisibleLimit();
}
function handleSearch(el) {
    searchTerm = el.value || "";
    applyFilters();
}
function loadMore() {
    visibleLimit += VISIBLE_STEP;
    applyVisibleLimit();
}
let autoLoading = false;
function tryAutoFill() {
    const btn = document.getElementById('loadMore');
    if (!btn || btn.style.display === 'none') return;
    const bodyShort = document.body.scrollHeight <= (window.innerHeight + 20);
    if (!bodyShort) return;
    autoLoading = true;
    loadMore();
    setTimeout(() => {
        autoLoading = false;
        tryAutoFill();
    }, 120);
}
function autoLoadOnScroll() {
    if (autoLoading) return;
    const btn = document.getElementById('loadMore');
    if (!btn || btn.style.display === 'none') return;
    const nearBottom = (window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 200);
    if (!nearBottom) return;
    autoLoading = true;
    loadMore();
    setTimeout(() => { autoLoading = false; }, 200);
}
function observeLoadMore() {
    const sentinel = document.getElementById('loadMoreSentinel');
    if (!sentinel || !('IntersectionObserver' in window)) return;
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !autoLoading) {
                autoLoading = true;
                loadMore();
                setTimeout(() => { autoLoading = false; }, 150);
            }
        });
    }, { root: null, rootMargin: '200px', threshold: 0.01 });
    observer.observe(sentinel);
}
function toggleBrandFilter(brand, checkbox) {
    if (!brand) return;
    if (checkbox && checkbox.checked) {
        brandFilter.add(brand);
    } else {
        brandFilter.delete(brand);
    }
    applyFilters();
}
function toggleType(type, btn) {
    if (activeTypes.has(type)) {
        activeTypes.delete(type);
        btn.classList.remove('active');
    } else {
        activeTypes.add(type);
        btn.classList.add('active');
    }
    saveFilterPrefs();
    applyFilters();
}
function toggleStrain(kind, btn) {
    if (activeStrains.has(kind)) {
        activeStrains.delete(kind);
        btn.classList.remove('active');
    } else {
        activeStrains.add(kind);
        btn.classList.add('active');
    }
    saveFilterPrefs();
    applyFilters();
}
function toggleFavorites(btn) {
    favoritesOnly = !favoritesOnly;
    btn.classList.toggle('active', favoritesOnly);
    applyFilters();
}
function toggleSmalls(btn) {
    showSmalls = !showSmalls;
    btn.classList.toggle('active', showSmalls);
    saveFilterPrefs();
    applyFilters();
}
function toggleOutOfStock(btn) {
    showOutOfStock = !showOutOfStock;
    btn.classList.toggle('active', showOutOfStock);
    applyFilters();
}
let favorites = new Set();
let basketTotal = 0;
let basketCount = 0;
let basket = new Map();
const DELIVERY_FEE = 4.99;
function refreshBasketButtons() {
    document.querySelectorAll('.card').forEach(card => {
        const key = card.dataset.key || card.dataset.favkey || card.dataset.productId || card.dataset.strain;
        const btn = card.querySelector('.btn-basket');
        if (!btn) return;
        const qty = (key && basket.has(key)) ? (basket.get(key).qty || 0) : 0;
        if (qty > 0) {
            btn.classList.add('added');
            btn.textContent = `${qty} in basket`;
        } else {
            btn.classList.remove('added');
            btn.textContent = 'Add to basket';
        }
    });
}
function updateBasketUI() {
    const c = document.getElementById('basketCount');
    const t = document.getElementById('basketTotal');
    basketCount = 0;
    basketTotal = 0;
    basket.forEach((item) => {
        basketCount += item.qty;
        basketTotal += item.price * item.qty;
    });
    if (basketCount > 0) {
        basketTotal += DELIVERY_FEE;
    }
    if (c) c.textContent = basketCount;
    if (t) t.textContent = basketTotal.toFixed(2);
}
function addToBasket(btn) {
    const card = btn.closest('.card');
    if (!card) return;
    const price = parseFloat(card.dataset.price);
    if (!Number.isFinite(price)) return;
    const key = card.dataset.key || card.dataset.favkey || card.dataset.productId || card.dataset.strain || String(Math.random());
    const name = (card.dataset.strain || "").trim();
    const brand = (card.dataset.brand || "").trim();
    const existing = basket.get(key);
    if (existing) {
        existing.qty += 1;
        basket.set(key, existing);
    } else {
        basket.set(key, { key, name, brand, price, qty: 1 });
    }
    updateBasketUI();
    renderBasketModal(false);
    refreshBasketButtons();
}
function toggleBasket() {
    renderBasketModal(true);
    const btn = document.getElementById('basketButton');
    if (btn) btn.classList.add('active');
}
function renderBasketModal(show) {
    let modal = document.getElementById('basketModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'basketModal';
        modal.className = 'basket-modal';
        document.body.appendChild(modal);
    }
    const rows = [];
    if (basket.size === 0) {
        rows.push("<div class='basket-empty'>Basket is empty.</div>");
    } else {
        basket.forEach((item) => {
            rows.push(`
            <div class='basket-row' data-key='${item.key}'>
              <div style='flex:1;'>
                <div><strong>${item.name || 'Item'}</strong></div>
                <div class='small'>${item.brand || ''}</div>
                <div class='small'>£${item.price.toFixed(2)}</div>
              </div>
              <input class='basket-qty' type='number' min='0' value='${item.qty}' onchange='updateBasketQty("${item.key}", this.value)' />
              <button class='btn-basket' onclick='removeFromBasket("${item.key}")'>Remove</button>
            </div>
            `);
        });
    }
    const feeLine = (basketCount > 0) ? `<div class='small'>Delivery: £${DELIVERY_FEE.toFixed(2)}</div>` : '';
    modal.innerHTML = `
      <div class='basket-panel'>
        <div class='basket-title'>Basket</div>
        ${rows.join("\\n")}
        <div style='margin-top:12px;display:flex;justify-content:space-between;align-items:center;'>
          <div>
            <div><strong>Total:</strong> £${basketTotal.toFixed(2)} (${basketCount} item${basketCount===1?"":"s"})</div>
            ${feeLine}
          </div>
          <button class='btn-basket' onclick='closeBasket()'>Close</button>
        </div>
      </div>
    `;
    if (show) {
        modal.style.display = 'flex';
    }
}
function closeBasket() {
    const modal = document.getElementById('basketModal');
    if (modal) modal.style.display = 'none';
    const btn = document.getElementById('basketButton');
    if (btn) btn.classList.remove('active');
}
function openImageModal(src, altText) {
    if (!src) return;
    let modal = document.getElementById('imageModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'imageModal';
        modal.className = 'image-modal';
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.style.display = 'none';
        });
        document.body.appendChild(modal);
    }
    const safeAlt = altText || '';
    modal.innerHTML = `<img src="${src}" alt="${safeAlt}" />`;
    modal.style.display = 'flex';
}
function updateBasketQty(key, val) {
    const qty = parseInt(val, 10);
    if (!basket.has(key)) return;
    if (!Number.isFinite(qty) || qty <= 0) {
        basket.delete(key);
    } else {
        const item = basket.get(key);
        item.qty = qty;
        basket.set(key, item);
    }
    updateBasketUI();
    renderBasketModal(false);
    refreshBasketButtons();
}
function removeFromBasket(key) {
    if (basket.has(key)) basket.delete(key);
    updateBasketUI();
    renderBasketModal(false);
    refreshBasketButtons();
}
function loadFavorites() {
    try {
        const rawNew = localStorage.getItem('ft_favs_global');
        const rawOld = localStorage.getItem('ft_favs');
        const cookie = (document.cookie || '').split(';').map(s=>s.trim()).find(s=>s.startsWith('ft_favs_global='));
        const cookieVal = cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : null;
        const arrNew = rawNew ? JSON.parse(rawNew) : [];
        const arrOld = rawOld ? JSON.parse(rawOld) : [];
        const arrCookie = cookieVal ? JSON.parse(cookieVal) : [];
        const merged = Array.from(new Set([...(Array.isArray(arrOld)?arrOld:[]), ...(Array.isArray(arrNew)?arrNew:[]), ...(Array.isArray(arrCookie)?arrCookie:[])]));
        favorites = new Set(merged);
    } catch (e) {}
}
function loadFilterPrefs() {
    try {
        const raw = localStorage.getItem('ft_filters');
        if (!raw) return;
        const data = JSON.parse(raw);
        if (Array.isArray(data.types)) {
            activeTypes = new Set(data.types);
        }
        if (Array.isArray(data.strains)) {
            activeStrains = new Set(data.strains);
        }
        if (typeof data.smalls === 'boolean') {
            showSmalls = data.smalls;
        }
        if (typeof data.outstock === 'boolean') {
            showOutOfStock = data.outstock;
        }
    } catch (e) {}
}
function saveFilterPrefs() {
    try {
        const payload = {
            types: Array.from(activeTypes),
            strains: Array.from(activeStrains),
            smalls: showSmalls,
            outstock: showOutOfStock,
        };
        localStorage.setItem('ft_filters', JSON.stringify(payload));
    } catch (e) {}
}
function saveFavorites() {
    try {
        localStorage.setItem('ft_favs_global', JSON.stringify(Array.from(favorites)));
        document.cookie = `ft_favs_global=${encodeURIComponent(JSON.stringify(Array.from(favorites)))}; path=/; max-age=${60*60*24*365}`;
    } catch (e) {}
}
function applyFavState(card) {
    if (!card) return;
    const key = card.dataset.favkey;
    const btn = card.querySelector('.fav-btn');
    const isFav = key && favorites.has(key);
    card.classList.toggle('card-fav', isFav);
    if (btn) {
        btn.textContent = isFav ? '★' : '☆';
        btn.classList.toggle('fav-on', isFav);
    }
}
function toggleFavorite(btn) {
    const card = btn.closest('.card');
    if (!card) return;
    const key = card.dataset.favkey;
    if (!key) return;
    if (favorites.has(key)) {
        favorites.delete(key);
    } else {
        favorites.add(key);
    }
    saveFavorites();
    applyFavState(card);
    // Immediately persist and reflect without needing refresh
    document.cookie = `ft_favs_global=${encodeURIComponent(JSON.stringify(Array.from(favorites)))}; path=/; max-age=${60*60*24*365}`;
}
function resetFilters() {
    activeTypes = new Set(['flower','oil','vape']);
    activeStrains = new Set(['Indica','Sativa','Hybrid']);
    document.querySelectorAll('.btn-filter').forEach(b => b.classList.add('active'));
    favoritesOnly = false;
    showSmalls = true;
    showOutOfStock = false;
    brandFilter = new Set();
    saveFilterPrefs();
    // Reset sliders
    const priceMinEl = document.getElementById('priceMinRange');
    const priceMaxEl = document.getElementById('priceMaxRange');
    const thcMinEl = document.getElementById('thcMinRange');
    const thcMaxEl = document.getElementById('thcMaxRange');
    if (priceMinEl && priceMaxEl) {
        priceMinSel = priceMinBound;
        priceMaxSel = priceMaxBound;
        priceMinEl.value = priceMinBound;
        priceMaxEl.value = priceMaxBound;
        priceMinEl.dispatchEvent(new Event('input'));
        priceMaxEl.dispatchEvent(new Event('input'));
    }
    if (thcMinEl && thcMaxEl) {
        thcMinSel = thcMinBound;
        thcMaxSel = thcMaxBound;
        thcMinEl.value = thcMinBound;
        thcMaxEl.value = thcMaxBound;
        thcMinEl.dispatchEvent(new Event('input'));
        thcMaxEl.dispatchEvent(new Event('input'));
    }
    document.querySelectorAll('[data-brand-option]').forEach(chk => { chk.checked = false; });
    applyFilters();
}
function applyTheme(saved) {
    const body = document.body;
    const useLight = saved === true || saved === 'light';
    body.classList.toggle('light', useLight);
    localStorage.setItem('ft_theme', useLight ? 'light' : 'dark');
    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = useLight ? 'Use dark theme' : 'Use light theme';
    // Swap type icons to match theme
    document.querySelectorAll('[data-theme-icon]').forEach(img => {
        const theme = img.getAttribute('data-theme-icon');
        img.style.display = theme === (useLight ? 'light' : 'dark') ? '' : 'none';
    });
}
function toggleTheme() {
    const current = localStorage.getItem('ft_theme') || 'dark';
    applyTheme(current !== 'light');
}
function toggleBrandMenu() {
    const menu = document.getElementById('brandMenu');
    if (menu) menu.classList.toggle('open');
}
function closeBrandMenu(e) {
    const menu = document.getElementById('brandMenu');
    const wrapper = document.getElementById('brandFilter');
    if (!menu || !wrapper) return;
    if (!wrapper.contains(e.target)) {
        menu.classList.remove('open');
    }
}
function buildBrandMenu() {
    const menu = document.getElementById('brandMenu');
    if (!menu) return;
    const brands = new Set();
    document.querySelectorAll('.card').forEach(c => {
        const brand = (c.dataset.brand || '').trim();
        if (brand) brands.add(brand);
    });
    const items = Array.from(brands).sort((a, b) => a.localeCompare(b));
    if (!items.length) {
        menu.innerHTML = "<div class='small'>No brands found.</div>";
        return;
    }
    menu.innerHTML = items.map(brand => (
        `<label class='brand-item'>
           <input type='checkbox' data-brand-option='1' data-brand='${brand.replace(/'/g, '&#39;')}'>
           <span>${brand}</span>
         </label>`
    )).join("");
    menu.querySelectorAll('input[data-brand-option]').forEach(chk => {
        chk.addEventListener('change', (e) => {
            const brand = e.currentTarget.getAttribute('data-brand') || '';
            toggleBrandFilter(brand, e.currentTarget);
        });
    });
}
document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('ft_theme');
applyTheme(saved === 'light');
    loadFilterPrefs();
    loadFavorites();
    document.querySelectorAll('.card').forEach(applyFavState);
    updateBasketUI();
    updateSortButtons();
    sortCards(state.key);
    // Init ranges
    const priceMinEl = document.getElementById('priceMinRange');
    const priceMaxEl = document.getElementById('priceMaxRange');
    const thcMinEl = document.getElementById('thcMinRange');
    const thcMaxEl = document.getElementById('thcMaxRange');
    const clamp = (val, min, max) => {
        const n = parseFloat(val);
        if (!Number.isFinite(n)) return min;
        return Math.min(Math.max(n, min), max);
    };
    const updatePriceLabel = () => {
        const label = document.getElementById('priceLabel');
        const minVal = document.getElementById('priceMinVal');
        const maxVal = document.getElementById('priceMaxVal');
        if (label) label.textContent = `£${priceMinSel.toFixed(0)} – £${priceMaxSel.toFixed(0)}`;
        if (minVal) minVal.textContent = `£${priceMinSel.toFixed(0)}`;
        if (maxVal) maxVal.textContent = `£${priceMaxSel.toFixed(0)}`;
    };
    const updateThcLabel = () => {
        const label = document.getElementById('thcLabel');
        const minVal = document.getElementById('thcMinVal');
        const maxVal = document.getElementById('thcMaxVal');
        if (label) label.textContent = `${thcMinSel.toFixed(0)}% – ${thcMaxSel.toFixed(0)}%`;
        if (minVal) minVal.textContent = `${thcMinSel.toFixed(0)}%`;
        if (maxVal) maxVal.textContent = `${thcMaxSel.toFixed(0)}%`;
    };
    if (priceMinEl && priceMaxEl) {
        priceMinEl.min = priceMinBound; priceMinEl.max = priceMaxBound; priceMinEl.value = priceMinBound;
        priceMaxEl.min = priceMinBound; priceMaxEl.max = priceMaxBound; priceMaxEl.value = priceMaxBound;
        const syncPrice = () => {
            priceMinSel = clamp(parseFloat(priceMinEl.value), priceMinBound, priceMaxBound);
            priceMaxSel = clamp(parseFloat(priceMaxEl.value), priceMinSel, priceMaxBound);
            if (parseFloat(priceMinEl.value) > priceMaxSel) priceMinEl.value = priceMaxSel;
            priceMaxEl.value = priceMaxSel;
            priceMinEl.value = priceMinSel;
            updatePriceLabel();
        };
        const applyPriceFilters = () => { syncPrice(); applyFilters(); };
        priceMinEl.addEventListener('input', syncPrice);
        priceMaxEl.addEventListener('input', syncPrice);
        priceMinEl.addEventListener('change', applyPriceFilters);
        priceMaxEl.addEventListener('change', applyPriceFilters);
        priceMinEl.addEventListener('mouseup', applyPriceFilters);
        priceMaxEl.addEventListener('mouseup', applyPriceFilters);
        priceMinEl.addEventListener('touchend', applyPriceFilters);
        priceMaxEl.addEventListener('touchend', applyPriceFilters);
        updatePriceLabel();
    }
    if (thcMinEl && thcMaxEl) {
        thcMinEl.min = thcMinBound; thcMinEl.max = thcMaxBound; thcMinEl.value = thcMinBound;
        thcMaxEl.min = thcMinBound; thcMaxEl.max = thcMaxBound; thcMaxEl.value = thcMaxBound;
        const syncThc = () => {
            thcMinSel = clamp(parseFloat(thcMinEl.value), thcMinBound, thcMaxBound);
            thcMaxSel = clamp(parseFloat(thcMaxEl.value), thcMinSel, thcMaxBound);
            if (parseFloat(thcMinEl.value) > thcMaxSel) thcMinEl.value = thcMaxSel;
            thcMaxEl.value = thcMaxSel;
            thcMinEl.value = thcMinSel;
            updateThcLabel();
        };
        const applyThcFilters = () => { syncThc(); applyFilters(); };
        thcMinEl.addEventListener('input', syncThc);
        thcMaxEl.addEventListener('input', syncThc);
        thcMinEl.addEventListener('change', applyThcFilters);
        thcMaxEl.addEventListener('change', applyThcFilters);
        thcMinEl.addEventListener('mouseup', applyThcFilters);
        thcMaxEl.addEventListener('mouseup', applyThcFilters);
        thcMinEl.addEventListener('touchend', applyThcFilters);
        thcMaxEl.addEventListener('touchend', applyThcFilters);
        updateThcLabel();
    }
    document.querySelectorAll('[data-filter-type]').forEach(btn => {
        const t = btn.getAttribute('data-filter-type');
        btn.classList.toggle('active', activeTypes.has(t));
    });
    document.querySelectorAll('[data-filter-strain]').forEach(btn => {
        const s = btn.getAttribute('data-filter-strain');
        btn.classList.toggle('active', activeStrains.has(s));
    });
    const smallsBtn = document.querySelector('[data-filter-smalls]');
    if (smallsBtn) smallsBtn.classList.toggle('active', showSmalls);
    const outstockBtn = document.querySelector('[data-filter-outstock]');
    if (outstockBtn) outstockBtn.classList.toggle('active', showOutOfStock);
    // Purge legacy stock filter preferences (in/low) if present.
    try {
        const raw = localStorage.getItem('ft_filters');
        if (raw) {
            const data = JSON.parse(raw);
            if (data && (data.instock !== undefined || data.lowstock !== undefined)) {
                delete data.instock;
                delete data.lowstock;
                localStorage.setItem('ft_filters', JSON.stringify(data));
            }
        }
    } catch (e) {}
    const meta = document.getElementById('exportMeta');
    if (meta) {
        const ts = document.body.getAttribute('data-exported') || '';
        const count = document.body.getAttribute('data-count') || '';
        if (meta) {
            const parts = [];
            if (count) parts.push(`${count} items`);
            if (ts) parts.push(`Updated ${ts}`);
            meta.textContent = parts.join(' • ');
        }
    }
    buildBrandMenu();
    document.addEventListener('click', closeBrandMenu);
    window.addEventListener('scroll', autoLoadOnScroll);
    applyFilters();
    observeLoadMore();
    setTimeout(tryAutoFill, 100);
});
</script>
</head><body>
<div class="export-header">
  <div>
    <h1>Available Medical Cannabis</h1>
    <div class="small" id="exportMeta"></div>
  </div>
</div>
<div class='controls'>
  <div class='controls-inner'>
    <button class='sort-btn' data-sort="price" onclick="sortCards('price', this)">Price</button>
    <button class='sort-btn' data-sort="thc" onclick="sortCards('thc', this)">THC</button>
    <button class='sort-btn' data-sort="cbd" onclick="sortCards('cbd', this)">CBD</button>
    <input class="search-box" type="text" placeholder="Search strain or producer" oninput="handleSearch(this)" />
    <button class='btn-filter active' data-filter-type="flower" onclick="toggleType('flower', this)">Flower</button>
    <button class='btn-filter active' data-filter-type="oil" onclick="toggleType('oil', this)">Oil</button>
    <button class='btn-filter active' data-filter-type="vape" onclick="toggleType('vape', this)">Vape</button>
    <button class='btn-filter active' data-filter-strain="Indica" onclick="toggleStrain('Indica', this)">Indica</button>
    <button class='btn-filter active' data-filter-strain="Sativa" onclick="toggleStrain('Sativa', this)">Sativa</button>
    <button class='btn-filter active' data-filter-strain="Hybrid" onclick="toggleStrain('Hybrid', this)">Hybrid</button>
    <button class='btn-filter' onclick="toggleFavorites(this)">Favorites</button>
    <button class='btn-filter active' data-filter-smalls="1" onclick="toggleSmalls(this)">Smalls</button>
    <button class='btn-filter' data-filter-outstock="1" onclick="toggleOutOfStock(this)">Out of stock</button>
    <div class="brand-filter" id="brandFilter">
      <button class="btn-filter" onclick="toggleBrandMenu()">Brands ▾</button>
      <div class="brand-menu" id="brandMenu"></div>
    </div>
    <button onclick="resetFilters()">Reset</button>
    <div class="range-group">
      <div class="range-line">
        <span class="range-val" id="priceMinVal"></span>
        <span class="range-tag">Min</span>
        <div class="range-slider">
          <input class="range-min" type="range" id="priceMinRange" step="1">
          <input class="range-max" type="range" id="priceMaxRange" step="1">
        </div>
        <span class="range-tag">Max</span>
        <span class="range-val" id="priceMaxVal"></span>
        <div class="range-title">Price</div>
      </div>
      <div class="range-values" id="priceLabel"></div>
    </div>
    <div class="range-group">
      <div class="range-line">
        <span class="range-val" id="thcMinVal"></span>
        <span class="range-tag">Min</span>
        <div class="range-slider">
          <input class="range-min" type="range" id="thcMinRange" step="1">
          <input class="range-max" type="range" id="thcMaxRange" step="1">
        </div>
        <span class="range-tag">Max</span>
        <span class="range-val" id="thcMaxVal"></span>
        <div class="range-title">THC %</div>
      </div>
      <div class="range-values" id="thcLabel"></div>
    </div>
  </div>
<div class='controls-right'>
    <button class="basket-button" id="basketButton" onclick="toggleBasket()">Basket: <span id="basketCount">0</span> | £<span id="basketTotal">0.00</span></button>
    <button id="themeToggle" onclick="toggleTheme()">Use light theme</button>
  </div>
</div>
<div class='grid' id='grid'>
__CARDS__
</div>
<div class='load-more'>
  <button id='loadMore' onclick='loadMore()'>Load more</button>
  <span class='small' id='visibleCount'></span>
</div>
<div id='loadMoreSentinel' style='height:1px'></div>
</body></html>"""
