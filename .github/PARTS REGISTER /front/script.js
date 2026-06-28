/* ═══════════════════════════════════════════════
   AIRCRAFT REMOVED PARTS REGISTER — script.js
   ═══════════════════════════════════════════════ */

'use strict';

const STORAGE_KEY = 'mro_removed_parts_v2';
let parts = [];

// ── INIT ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setHeaderDate();
  loadFromStorage();
  renderTable();
  updateBadge();
  setupDragDrop('partPhotoBox',  'partPhotoInput',  'partPhotoPreview',  'clearPartBtn');
  setupDragDrop('platePhotoBox', 'platePhotoInput', 'platePhotoPreview', 'clearPlateBtn');
});

// ── DATE: DD.MM.YY ───────────────────────────────
function todayFormatted() {
  const d  = new Date();
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yy = String(d.getFullYear()).slice(2);
  return `${dd}.${mm}.${yy}`;
}

function setHeaderDate() {
  const el   = document.getElementById('currentDate');
  const d    = new Date();
  const opts = { year: 'numeric', month: 'short', day: '2-digit', weekday: 'short' };
  el.textContent = d.toLocaleDateString('en-US', opts).toUpperCase();
}

// ── STORAGE ──────────────────────────────────────
function saveToStorage() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(parts));
  } catch (e) {
    showToast('⚠ Storage full — photos may be too large.');
  }
}

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) parts = JSON.parse(raw);
  } catch (e) {
    parts = [];
  }
}

// ── PHOTO HANDLING ───────────────────────────────
// Compress image to base64 (max 800px wide, quality 0.72)
function compressImage(file, callback) {
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = new Image();
    img.onload = () => {
      const MAX = 800;
      let w = img.width, h = img.height;
      if (w > MAX) { h = Math.round(h * MAX / w); w = MAX; }
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      canvas.getContext('2d').drawImage(img, 0, 0, w, h);
      callback(canvas.toDataURL('image/jpeg', 0.72));
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function previewPhoto(inputId, previewId, boxId, clearBtnId) {
  const file = document.getElementById(inputId).files[0];
  if (!file) return;
  compressImage(file, (dataUrl) => {
    const preview = document.getElementById(previewId);
    const box     = document.getElementById(boxId);
    preview.src   = dataUrl;
    preview.style.display = 'block';
    box.classList.add('has-photo');
    if (clearBtnId) document.getElementById(clearBtnId).style.display = 'inline-flex';
  });
}

function clearPhoto(inputId, previewId, boxId, clearBtnId) {
  document.getElementById(inputId).value   = '';
  const preview = document.getElementById(previewId);
  preview.src   = '';
  preview.style.display = 'none';
  document.getElementById(boxId).classList.remove('has-photo');
  document.getElementById(clearBtnId).style.display = 'none';
}

function setupDragDrop(boxId, inputId, previewId, clearBtnId) {
  const box = document.getElementById(boxId);
  box.addEventListener('dragover',  (e) => { e.preventDefault(); box.classList.add('drag-over'); });
  box.addEventListener('dragleave', ()  => box.classList.remove('drag-over'));
  box.addEventListener('drop', (e) => {
    e.preventDefault();
    box.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (!file || !file.type.startsWith('image/')) return;
    const input = document.getElementById(inputId);
    const dt    = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    previewPhoto(inputId, previewId, boxId, clearBtnId);
  });
}

// ── ADD PART ─────────────────────────────────────
function addPart() {
  const acReg     = v('acReg');
  const pn        = v('pn');
  const sn        = v('sn');
  const pos       = v('pos');
  const qty       = v('qty') || '1';
  const removedBy = v('removedBy');

  if (!pn) { shake('pn'); showToast('⚠ Part Number (P/N) is required.'); return; }
  if (!qty || Number(qty) < 1) { shake('qty'); showToast('⚠ Quantity must be ≥ 1.'); return; }

  // Capture photo data from previews
  const partPhoto  = document.getElementById('partPhotoPreview').src  || '';
  const platePhoto = document.getElementById('platePhotoPreview').src || '';

  const entry = {
    no:         parts.length + 1,
    date:       todayFormatted(),
    acReg, pn, sn, pos, qty, removedBy,
    partPhoto:  partPhoto.startsWith('data:') ? partPhoto  : '',
    platePhoto: platePhoto.startsWith('data:') ? platePhoto : '',
    id:         Date.now()
  };

  parts.push(entry);
  saveToStorage();
  renderTable();
  updateBadge();
  resetForm();
  showToast('✔ Part registered successfully.');
}

// ── DELETE ───────────────────────────────────────
function deletePart(id) {
  if (!confirm('Delete this entry? This cannot be undone.')) return;
  parts = parts.filter(p => p.id !== id);
  renumber();
  saveToStorage();
  renderTable();
  updateBadge();
  showToast('🗑 Entry deleted.');
}

function renumber() {
  parts.forEach((p, i) => { p.no = i + 1; });
}

function clearAll() {
  if (!confirm('Delete ALL entries? This cannot be undone.')) return;
  parts = [];
  saveToStorage();
  renderTable();
  updateBadge();
  showToast('🗑 All entries cleared.');
}

// ── RENDER TABLE ─────────────────────────────────
function renderTable() {
  const query   = (document.getElementById('searchInput').value || '').toLowerCase().trim();
  const tbody   = document.getElementById('partsBody');
  const empty   = document.getElementById('emptyState');
  const table   = document.getElementById('partsTable');
  const countEl = document.getElementById('totalCount');

  const filtered = query
    ? parts.filter(p =>
        p.pn.toLowerCase().includes(query)    ||
        (p.sn    || '').toLowerCase().includes(query) ||
        (p.acReg || '').toLowerCase().includes(query)
      )
    : parts;

  countEl.textContent = filtered.length;

  if (filtered.length === 0) {
    tbody.innerHTML = '';
    table.style.display = 'none';
    empty.style.display = 'block';
    return;
  }

  table.style.display = '';
  empty.style.display = 'none';

  tbody.innerHTML = filtered.map(p => `
    <tr data-id="${p.id}">
      <td class="no-cell">${p.no}</td>
      <td class="date-cell">${esc(p.date)}</td>
      <td class="mono">${highlight(esc(p.acReg), query)}</td>
      <td class="mono pn-cell">${highlight(esc(p.pn), query)}</td>
      <td class="mono">${highlight(esc(p.sn), query)}</td>
      <td>${esc(p.pos)}</td>
      <td class="qty-cell">${esc(p.qty)}</td>
      <td>${esc(p.removedBy)}</td>
      <td class="photo-cell">
        ${p.partPhoto
          ? `<img src="${p.partPhoto}" class="thumb" onclick="openLightbox('${p.id}','part')" title="View Part Photo" />`
          : '<span class="no-photo">—</span>'}
      </td>
      <td class="photo-cell">
        ${p.platePhoto
          ? `<img src="${p.platePhoto}" class="thumb" onclick="openLightbox('${p.id}','plate')" title="View Plate Photo" />`
          : '<span class="no-photo">—</span>'}
      </td>
      <td style="text-align:center;">
        <button class="del-btn" onclick="deletePart(${p.id})" title="Delete">✕</button>
      </td>
    </tr>
  `).join('');
}

// ── LIGHTBOX ─────────────────────────────────────
function openLightbox(id, type) {
  const part = parts.find(p => p.id === Number(id));
  if (!part) return;
  const src     = type === 'part' ? part.partPhoto : part.platePhoto;
  const caption = type === 'part'
    ? `Part Photo — P/N: ${part.pn}${part.sn ? ' / S/N: ' + part.sn : ''}`
    : `Plate / Tag Photo — P/N: ${part.pn}${part.sn ? ' / S/N: ' + part.sn : ''}`;
  document.getElementById('lightboxImg').src         = src;
  document.getElementById('lightboxCaption').textContent = caption;
  document.getElementById('lightbox').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeLightbox(e) {
  if (e && e.target !== document.getElementById('lightbox') &&
           !e.target.classList.contains('lightbox-close')) return;
  document.getElementById('lightbox').classList.remove('open');
  document.getElementById('lightboxImg').src = '';
  document.body.style.overflow = '';
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.getElementById('lightbox').classList.remove('open');
    document.getElementById('lightboxImg').src = '';
    document.body.style.overflow = '';
  }
});

// ── SEARCH ───────────────────────────────────────
function highlight(text, query) {
  if (!query) return text;
  const re = new RegExp(`(${escapeRegExp(query)})`, 'gi');
  return text.replace(re, '<mark style="background:#fff3b0;color:#1a2535;border-radius:2px;padding:0 1px;">$1</mark>');
}
function escapeRegExp(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
function clearSearch() { document.getElementById('searchInput').value = ''; renderTable(); }

// ── CSV EXPORT ───────────────────────────────────
function exportCSV() {
  if (parts.length === 0) { showToast('⚠ No data to export.'); return; }
  const headers = ['No.','Date','A/C Reg.','P/N','S/N','POS','Qty','Removed By','Part Photo','Plate Photo'];
  const rows = parts.map(p => [
    p.no, p.date, p.acReg, p.pn, p.sn, p.pos, p.qty, p.removedBy,
    p.partPhoto  ? '[image attached]' : '',
    p.platePhoto ? '[image attached]' : ''
  ].map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`));

  const bom     = '\uFEFF';
  const csvBody = [headers.join(','), ...rows.map(r => r.join(','))].join('\r\n');
  const blob    = new Blob([bom + csvBody], { type: 'text/csv;charset=utf-8;' });
  const url     = URL.createObjectURL(blob);
  const a       = document.createElement('a');
  a.href        = url;
  a.download    = `RemovedParts_${todayFormatted()}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  showToast('📥 CSV downloaded.');
}

// ── FORM HELPERS ─────────────────────────────────
function v(id) { return document.getElementById(id).value.trim(); }

function resetForm() {
  ['acReg','pn','sn','pos','qty','removedBy'].forEach(id => {
    const el = document.getElementById(id);
    el.value = id === 'qty' ? '1' : '';
  });
  clearPhoto('partPhotoInput',  'partPhotoPreview',  'partPhotoBox',  'clearPartBtn');
  clearPhoto('platePhotoInput', 'platePhotoPreview', 'platePhotoBox', 'clearPlateBtn');
  document.getElementById('acReg').focus();
}

function updateBadge() {
  document.getElementById('totalBadge').textContent =
    parts.length === 1 ? '1 Part' : `${parts.length} Parts`;
}

// ── SHAKE ────────────────────────────────────────
function shake(id) {
  const el = document.getElementById(id);
  el.style.borderColor = '#e74c3c';
  el.style.animation   = 'none';
  el.offsetHeight;
  el.style.animation   = 'shake 0.38s ease';
  el.addEventListener('animationend', () => {
    el.style.borderColor = '';
    el.style.animation   = '';
  }, { once: true });
}
const shakeCSS = document.createElement('style');
shakeCSS.textContent = `
  @keyframes shake {
    0%,100% { transform:translateX(0); }
    20%      { transform:translateX(-5px); }
    40%      { transform:translateX(5px); }
    60%      { transform:translateX(-4px); }
    80%      { transform:translateX(4px); }
  }`;
document.head.appendChild(shakeCSS);

// ── TOAST ────────────────────────────────────────
let toastTimer;
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
}

// ── SANITIZE ─────────────────────────────────────
function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Enter on last field
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.id === 'removedBy') addPart();
});
