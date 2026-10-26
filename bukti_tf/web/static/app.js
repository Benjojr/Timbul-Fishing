(() => {
"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const S = {
  receipt: null, cover: [], loaded: null, dirty: false, busy: false,
  candidates: [], check: null, excelRow: null, receiptText: null, hasReport: false,
  evalSeq: 0, evalTimer: null, hist: { y: 0, m: 0 }, monthExcel: "", monthRows: 0, previewUrl: null,
};
const HARI = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
const BULAN = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"];
const PLACEHOLDER = "Belum ada gambar\n\nTempel (Ctrl+V), seret file ke sini,\natau pilih file";

// ---------------------------------------------------------------- util
const pad = n => String(n).padStart(2, "0");
const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const parseISO = t => { const [y, m, d] = t.split("-").map(Number); return new Date(y, m - 1, d); };
const todayISO = () => iso(new Date());
const addDays = (t, n) => { const d = parseISO(t); d.setDate(d.getDate() + n); return iso(d); };
const fmtDate = t => { const [y, m, d] = t.split("-"); return `${d}/${m}/${y}`; };
const titik = n => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
const rupiah = n => (n == null ? "-" : "Rp " + titik(n));
const setStatus = msg => { $("#status").textContent = msg; };

// Bilah progres atas: muncul hanya bila permintaan > 300 ms (supaya tidak berkedip pada yang cepat).
let inflight = 0, busyTimer = null;
const busyStart = () => { if (++inflight === 1) busyTimer = setTimeout(() => $("#busybar").classList.add("on"), 300); };
const busyEnd = () => { if (--inflight <= 0) { inflight = 0; clearTimeout(busyTimer); $("#busybar").classList.remove("on"); } };

async function api(path, { method = "GET", json, body, bar = true } = {}) {
  const headers = { "X-BuktiTF": "1" };
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (bar) busyStart();
  try {
    const res = await fetch(path, { method, headers, body });
    let data = null;
    try { data = await res.clone().json(); } catch { /* bukan JSON */ }
    if (!res.ok) {
      const err = new Error((data && data.error) || `Kesalahan ${res.status}`);
      err.status = res.status; err.data = data || {};
      throw err;
    }
    return data !== null ? data : res;
  } finally {
    if (bar) busyEnd();
  }
}

function on(el, ev, fn) {
  el.addEventListener(ev, async e => {
    try { await fn(e); } catch (err) { setStatus(err.message || String(err)); }
  });
}

async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return true; }
  } catch { /* lanjut ke cara lama */ }
  const ta = document.createElement("textarea");
  ta.value = text; ta.style.cssText = "position:fixed;opacity:0";
  document.body.appendChild(ta); ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { /* abaikan */ }
  ta.remove();
  return ok;
}

function download(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

// ---------------------------------------------------------------- form
const field = key => $(`[data-key="${key}"]`);

function readForm() {
  return {
    tanggal: $("#tanggal").value,
    sesi: [0, 1, 2].map(i => ({ peserta: field("peserta" + i).value, harga: field("harga" + i).value })),
    hadiah: $("#hadiah").value,
    rincian: $$("#expRows .exp").map(r => ({ keperluan: r.children[0].value, nominal: r.children[1].value })),
    catatan: $("#catatan").value,
  };
}

function writeForm(f) {
  $("#tanggal").value = f.tanggal;
  f.sesi.forEach((s, i) => { field("peserta" + i).value = s.peserta; field("harga" + i).value = s.harga; });
  $("#hadiah").value = f.hadiah;
  $("#catatan").value = f.catatan;
  $("#expRows").replaceChildren();
  (f.rincian.length ? f.rincian : [{ keperluan: "", nominal: "" }]).forEach(r => addExpense(r.keperluan, r.nominal));
}

function emptyForm(tanggal) {
  return { tanggal, sesi: [0, 1, 2].map(() => ({ peserta: "", harga: "" })), hadiah: "", rincian: [], catatan: "" };
}

function formatMoney(e) {
  const text = e.value, digits = text.replace(/\D/g, "");
  const formatted = digits ? titik(digits) : "";
  if (formatted === text) return;
  const cur = e.selectionStart ?? text.length;
  const left = text.slice(0, cur).replace(/\D/g, "").length;
  let nc = 0, seen = 0;
  for (let i = 0; i < formatted.length; i++) {
    if (seen === left) break;
    if (/\d/.test(formatted[i])) seen++;
    nc = i + 1;
  }
  e.value = formatted;
  e.setSelectionRange(nc, nc);
}

function addExpense(keperluan = "", nominal = "", focus = false) {
  const row = document.createElement("div");
  row.className = "exp";
  const k = document.createElement("input"), n = document.createElement("input"), x = document.createElement("button");
  k.className = "left"; k.placeholder = "Keperluan"; k.maxLength = 80; k.value = keperluan;
  n.className = "money"; n.placeholder = "Nominal"; n.inputMode = "numeric"; n.maxLength = 15; n.value = nominal;
  x.type = "button"; x.title = "Hapus baris"; x.textContent = "✕";
  row.append(k, n, x);
  $("#expRows").appendChild(row);
  if (focus) k.focus();
}

function markInvalid(keys) {
  $$("input.invalid").forEach(i => i.classList.remove("invalid"));
  for (const key of keys || []) {
    const m = /^rincian(\d+)$/.exec(key);
    const el = m ? ($$("#expRows .exp")[+m[1]] || {}).children?.[1] : field(key);
    if (el) el.classList.add("invalid");
  }
}

// ---------------------------------------------------------------- evaluasi (hitung + cek di server)
function scheduleEval(delay = 250) { clearTimeout(S.evalTimer); S.evalTimer = setTimeout(() => evaluate(), delay); }

async function evaluate(quiet = false) {
  clearTimeout(S.evalTimer);
  const seq = ++S.evalSeq;
  let r;
  try {
    r = await api("/api/evaluate", { method: "POST", json: { form: readForm(), receipt: S.receipt, cover: S.cover } });
  } catch (e) { if (seq === S.evalSeq) setStatus(e.message); return null; }
  if (seq !== S.evalSeq) return null;
  Object.assign(S, { hasReport: !!r.report, candidates: r.candidates, check: r.check,
                     excelRow: r.excel_row, receiptText: r.receipt_text });
  markInvalid(r.invalid);
  renderReport(r.report);
  renderCheck(r.check);
  updateState();
  updateButtons();
  if (!quiet) {
    if (r.warning) setStatus(r.warning);
    else if (!r.report) setStatus("Input rekap tidak valid");
    else if (S.receipt) setStatus("Pencocokan: " + r.check.label);
  }
  return r;
}

function renderReport(r) {
  const subs = $$(".sub");
  if (!r) {
    subs.forEach(s => { s.textContent = "-"; });
    ["tMasuk", "tKeluar", "tSisa"].forEach(id => { $("#" + id).textContent = "-"; });
    $("#tSisa").classList.remove("neg");
    $("#expTotal").textContent = "";
    return;
  }
  subs.forEach((s, i) => { s.textContent = r.subtotals[i]; });
  $("#tMasuk").textContent = r.pemasukan;
  $("#tKeluar").textContent = r.pengeluaran;
  $("#tSisa").textContent = r.sisa;
  $("#tSisa").classList.toggle("neg", r.sisa_negatif);
  $("#expTotal").textContent = r.rincian ? "Subtotal " + r.rincian : "";
}

function renderCheck(c) {
  const b = $("#cBadge");
  b.textContent = c.label; b.className = "pill " + c.tone;
  $("#cDetail").textContent = c.detail;
}

function renderReceipt() {
  const r = S.receipt, st = $("#rStatus");
  if (!r) {
    st.textContent = "-"; st.className = "pill idle";
    ["rWaktu", "rKe", "rNama", "rNominal"].forEach(id => { $("#" + id).textContent = "-"; });
  } else {
    const [txt, tone] = r.status === "berhasil" ? ["BERHASIL", "ok"] : r.status === "gagal" ? ["GAGAL", "bad"] : ["TIDAK TERBACA", "idle"];
    st.textContent = txt; st.className = "pill " + tone;
    $("#rWaktu").textContent = r.waktu; $("#rKe").textContent = r.ke;
    $("#rNama").textContent = r.nama; $("#rNominal").textContent = rupiah(r.nominal);
  }
  updateButtons();
}

function updateState() {
  const el = $("#stateLbl"), t = $("#tanggal").value;
  if (!t) { el.textContent = "Pilih tanggal"; el.className = "pill bad"; return; }
  const hari = HARI[parseISO(t).getDay()];
  if (S.loaded === t && !S.dirty) { el.textContent = `${hari} · Tersimpan`; el.className = "pill ok"; }
  else if (S.loaded === t) { el.textContent = `${hari} · Belum disimpan (ada perubahan)`; el.className = "pill warn"; }
  else { el.textContent = `${hari} · Belum disimpan`; el.className = "pill idle"; }
}

function updateButtons() {
  const free = !S.busy, rec = !!S.receipt && free;
  $("#saveBtn").disabled = !(S.hasReport && free);
  $("#excelBtn").disabled = !(S.hasReport && S.excelRow);
  $("#combineBtn").disabled = !(S.candidates.length && free);
  $("#copyReceiptBtn").disabled = !rec;
  $("#txtBtn").disabled = !rec;
  ["pickBtn", "pasteBtn", "newBtn"].forEach(id => { $("#" + id).disabled = !free; });
}

// ---------------------------------------------------------------- pratinjau & OCR
function showPreview(file) {
  clearPreview();
  S.previewUrl = URL.createObjectURL(file);
  const img = $("#preview");
  img.src = S.previewUrl; img.hidden = false; $("#dropText").hidden = true;
}

function clearPreview(msg) {
  if (S.previewUrl) { URL.revokeObjectURL(S.previewUrl); S.previewUrl = null; }
  $("#preview").hidden = true; $("#preview").removeAttribute("src");
  const t = $("#dropText"); t.hidden = false; t.textContent = msg || PLACEHOLDER;
}

function setBusy(b) { S.busy = b; $("#spin").hidden = !b; updateButtons(); }

async function processImage(file) {
  if (S.busy) return;
  if (!file || !file.type.startsWith("image/")) { setStatus("Berkas itu bukan gambar"); return; }
  Object.assign(S, { receipt: null, cover: [], candidates: [] });
  showPreview(file); renderReceipt(); evaluate(true);
  setBusy(true); setStatus(`Memproses ${file.name || "gambar dari clipboard"}...`);
  const fd = new FormData();
  fd.append("image", file, file.name || "bukti.png");
  let res;
  try { res = await api("/api/ocr", { method: "POST", body: fd, bar: false }); }
  catch (e) { setBusy(false); setStatus("Gagal memproses gambar"); alert(e.message); return; }
  setBusy(false);
  S.receipt = res.receipt; S.cover = []; S.dirty = true;
  renderReceipt();
  const r = await evaluate();
  if (r && !r.report) setStatus("Bukti terbaca. Perbaiki isian rekap untuk pencocokan.");
  else if (r && r.check.status === "gabungan") openCombine();
}

async function pasteFromButton() {
  if (!navigator.clipboard || !navigator.clipboard.read) {
    setStatus("Browser ini tidak mengizinkan tombol Tempel di sini. Tekan Ctrl+V."); return;
  }
  for (const item of await navigator.clipboard.read()) {
    const type = item.types.find(t => t.startsWith("image/"));
    if (type) { const blob = await item.getType(type); return processImage(new File([blob], "clipboard.png", { type })); }
  }
  setStatus("Clipboard tidak berisi gambar");
}

// ---------------------------------------------------------------- muat / simpan / baru
async function fetchRecord(t) { return (await api("/api/record?tanggal=" + encodeURIComponent(t))).record; }

function loadRecord(rec) {
  writeForm(rec.form);
  Object.assign(S, { receipt: rec.receipt, cover: rec.cover, loaded: rec.form.tanggal, dirty: false, candidates: [] });
  clearPreview(rec.receipt ? "Gambar bukti tidak disimpan" : null);
  renderReceipt(); updateState();
  evaluate(true);
  setStatus(`Data ${fmtDate(rec.form.tanggal)} dimuat`);
}

function resetForm(tanggal) {
  writeForm(emptyForm(tanggal));
  Object.assign(S, { receipt: null, cover: [], candidates: [], loaded: null, dirty: false });
  clearPreview(); renderReceipt(); evaluate(true);
  setStatus("Form dikosongkan");
}

async function navigateTo(t) {  // tombol ‹ › / Hari ini: muat data tanggal itu, atau form kosong
  if (S.dirty && !confirm("Isian yang belum disimpan akan hilang. Lanjutkan?")) return;
  const rec = await fetchRecord(t);
  if (rec) loadRecord(rec); else resetForm(t);
}

async function onDateTyped() {  // tanggal diubah langsung: isian dibiarkan, kecuali tanggal itu sudah ada datanya
  const t = $("#tanggal").value;
  if (!t || t === S.loaded) { updateState(); return; }
  const rec = await fetchRecord(t);
  if (!rec) { S.dirty = true; updateState(); scheduleEval(0); return; }
  if (S.dirty && !confirm(`Tanggal ${fmtDate(t)} sudah punya data tersimpan.\n\nMemuatnya akan mengganti isian yang sekarang (belum disimpan). Lanjutkan?`)) {
    updateState(); return;
  }
  loadRecord(rec);
}

async function save(overwrite = false) {
  if (!S.hasReport) { setStatus("Perbaiki isian yang ditandai merah dulu"); return; }
  let r;
  try {
    r = await api("/api/record", { method: "POST",
      json: { form: readForm(), receipt: S.receipt, cover: S.cover, loaded: S.loaded, overwrite } });
  } catch (e) {
    if (e.status === 409 && e.data.needs_confirm) {
      if (confirm(`${e.message}\nTimpa dengan isian sekarang?`)) return save(true);
      return;
    }
    alert(e.message); return;
  }
  Object.assign(S, { loaded: r.saved, dirty: false, receipt: r.receipt, cover: r.cover, candidates: [] });
  if (r.warning) alert(r.warning);
  renderReceipt();
  await evaluate(true);
  setStatus(`Rekap ${fmtDate(r.saved)} tersimpan`);
  if (currentTab() === "riwayat") refreshHistory();
}

// ---------------------------------------------------------------- gabungan
function openCombine() {
  if (!S.receipt || !S.candidates.length) return;
  $("#combineTitle").textContent = `Transfer ${rupiah(S.receipt.nominal)} cocok dengan:`;
  $("#combineList").replaceChildren(...S.candidates.map((c, i) => {
    const label = document.createElement("label"), radio = document.createElement("input");
    radio.type = "radio"; radio.name = "cand"; radio.value = i; radio.checked = i === 0;
    label.append(radio, c.text);
    return label;
  }));
  $("#combineDlg").showModal();
}

async function applyDays(days) {
  let r;
  try { r = await api("/api/apply", { method: "POST", json: { form: readForm(), receipt: S.receipt, days } }); }
  catch (e) { alert(e.message); return; }
  if (r.includes_form) {
    Object.assign(S, { cover: r.cover, loaded: $("#tanggal").value, dirty: false });
  } else {  // bukti dipakai hari lain; form ini tidak ikut
    Object.assign(S, { receipt: null, cover: [] });
    clearPreview(); renderReceipt();
  }
  S.candidates = [];
  await evaluate(true);
  setStatus(`Bukti diterapkan untuk ${r.text}`);
  if (currentTab() === "riwayat") refreshHistory();
}

// ---------------------------------------------------------------- riwayat
const currentTab = () => ($("#tab-riwayat").hidden ? "rekap" : "riwayat");

function showTab(name) {
  $$(".tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  $("#tab-rekap").hidden = name !== "rekap";
  $("#tab-riwayat").hidden = name !== "riwayat";
  if (name === "riwayat") {
    const t = $("#tanggal").value;
    if (t) { const d = parseISO(t); S.hist = { y: d.getFullYear(), m: d.getMonth() + 1 }; }
    refreshHistory().catch(e => setStatus(e.message));
  }
}

async function refreshHistory() {
  const { y, m } = S.hist;
  $("#histTitle").textContent = `${BULAN[m - 1]} ${y}`;
  const r = await api(`/api/month?year=${y}&month=${m}`);
  S.monthExcel = r.excel; S.monthRows = r.rows.length;
  $("#histTable tbody").replaceChildren(...r.rows.map(row => {
    const tr = document.createElement("tr");
    tr.dataset.tanggal = row.tanggal;
    [row.hari, row.masuk, row.keluar, row.sisa, row.ket, "✕"].forEach((v, i) => {
      const td = document.createElement("td");
      td.textContent = v;
      if (i >= 1 && i <= 3) td.className = "r";
      if (i === 4 && row.tone) td.className = "tone-" + row.tone;
      if (i === 5) { td.className = "x"; td.title = "Hapus rekap ini"; }
      tr.appendChild(td);
    });
    return tr;
  }));
  $("#histEmpty").hidden = r.rows.length > 0;
  $("#histTable").hidden = r.rows.length === 0;
  $("#histTotal").textContent = r.summary || "Belum ada data tersimpan di bulan ini.";
  const pdf = $("#pdfLink");
  pdf.href = r.rows.length ? `/api/month.pdf?year=${y}&month=${m}` : "#";
  pdf.setAttribute("aria-disabled", r.rows.length ? "false" : "true");
}

async function openRecord(t) {
  if (S.dirty && t !== S.loaded && !confirm("Isian yang sekarang belum disimpan dan akan diganti. Lanjutkan?")) return;
  const rec = await fetchRecord(t);
  if (!rec) return;
  loadRecord(rec); showTab("rekap");
}

async function deleteRecord(t) {
  if (!confirm(`Hapus rekap tanggal ${fmtDate(t)}?`)) return;
  await api("/api/record?tanggal=" + encodeURIComponent(t), { method: "DELETE" });
  if (S.loaded === t) {
    S.loaded = null; S.cover = S.cover.filter(x => x !== t);
    updateState(); evaluate(true);
  }
  await refreshHistory();
  setStatus(`Rekap ${fmtDate(t)} dihapus`);
}

function shiftMonth(delta) {
  const idx = S.hist.y * 12 + (S.hist.m - 1) + delta;
  S.hist = { y: Math.floor(idx / 12), m: (idx % 12) + 1 };
  return refreshHistory();
}

// ---------------------------------------------------------------- pasang event
function wire() {
  // isian rekap
  $("#tab-rekap").addEventListener("input", e => {
    const t = e.target;
    if (t.tagName !== "INPUT" || t.id === "tanggal") return;
    if (t.classList.contains("money")) formatMoney(t);
    S.dirty = true; updateState(); scheduleEval();
  });
  $("#tab-rekap").addEventListener("keydown", e => {
    const t = e.target;
    if (e.key !== "Enter" || t.tagName !== "INPUT" || t.type === "date") return;
    e.preventDefault();
    const inputs = $$(".scroll input", $("#tab-rekap")).filter(i => i.type !== "date");
    const row = t.closest(".exp");
    if (row && t === row.children[1] && row === $("#expRows").lastElementChild
        && (row.children[0].value.trim() || t.value.trim())) { addExpense("", "", true); return; }
    const next = inputs[inputs.indexOf(t) + 1];
    if (next) { next.focus(); next.select(); }
  });
  on($("#expRows"), "click", e => {
    if (e.target.tagName !== "BUTTON") return;
    e.target.closest(".exp").remove();
    if (!$("#expRows").children.length) addExpense();
    S.dirty = true; updateState(); scheduleEval(0);
  });
  on($("#addExp"), "click", () => { addExpense("", "", true); });
  on($("#tanggal"), "change", onDateTyped);
  on($("#prevDay"), "click", () => navigateTo(addDays($("#tanggal").value || todayISO(), -1)));
  on($("#nextDay"), "click", () => navigateTo(addDays($("#tanggal").value || todayISO(), 1)));
  on($("#todayBtn"), "click", () => navigateTo(todayISO()));

  // aksi
  on($("#saveBtn"), "click", () => save());
  on($("#newBtn"), "click", () => {
    if (S.dirty && !confirm("Isian yang belum disimpan akan hilang. Lanjutkan?")) return;
    resetForm(todayISO());
  });
  on($("#excelBtn"), "click", async () => {
    if (!S.excelRow) { setStatus("Perbaiki isian yang ditandai merah dulu"); return; }
    const checked = S.check && S.check.status === "checked";
    const ok = await copyText(S.excelRow);
    setStatus(ok ? `Baris ${fmtDate($("#tanggal").value)} disalin ke clipboard` + (checked ? " (Keterangan: Checked)" : " (tanpa Checked)")
                 : "Gagal menyalin ke clipboard");
  });
  on($("#combineBtn"), "click", openCombine);
  on($("#combineCancel"), "click", () => $("#combineDlg").close("cancel"));
  on($("#combineDlg"), "close", async () => {
    const dlg = $("#combineDlg");
    if (dlg.returnValue !== "ok") return;
    const picked = $("input[name=cand]:checked", dlg);
    if (picked) await applyDays(S.candidates[+picked.value].days);
  });

  // bukti
  on($("#pickBtn"), "click", () => $("#file").click());
  on($("#file"), "change", async e => { const f = e.target.files[0]; e.target.value = ""; if (f) await processImage(f); });
  on($("#pasteBtn"), "click", pasteFromButton);
  document.addEventListener("paste", e => {
    const f = [...(e.clipboardData?.files || [])].find(x => x.type.startsWith("image/"));
    if (f) { e.preventDefault(); processImage(f).catch(err => setStatus(err.message)); }
    else if (!/^(INPUT|TEXTAREA)$/.test(e.target.tagName)) setStatus("Clipboard tidak berisi gambar");
  });
  const drop = $("#drop");
  ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => { const f = e.dataTransfer.files[0]; if (f) processImage(f).catch(err => setStatus(err.message)); });
  on($("#copyReceiptBtn"), "click", async () => {
    setStatus((S.receiptText && await copyText(S.receiptText)) ? "Hasil bukti disalin ke clipboard" : "Gagal menyalin ke clipboard");
  });
  on($("#txtBtn"), "click", async () => {
    const res = await api("/api/receipt/txt", { method: "POST", json: { receipt: S.receipt } });
    download(await res.blob(), "bukti-transfer.txt");
    setStatus("bukti-transfer.txt diunduh");
  });

  // riwayat
  $$(".tabs button").forEach(b => on(b, "click", () => showTab(b.dataset.tab)));
  on($("#prevMonth"), "click", () => shiftMonth(-1));
  on($("#nextMonth"), "click", () => shiftMonth(1));
  on($("#histTable"), "click", async e => {
    const tr = e.target.closest("tr");
    if (!tr || !tr.dataset.tanggal) return;
    if (e.target.classList.contains("x")) await deleteRecord(tr.dataset.tanggal);
    else await openRecord(tr.dataset.tanggal);
  });
  on($("#monthExcelBtn"), "click", async () => {
    if (!S.monthRows) { setStatus("Tidak ada data untuk disalin"); return; }
    const ok = await copyText(S.monthExcel);
    setStatus(ok ? `${S.monthRows} baris (${BULAN[S.hist.m - 1]}) disalin ke clipboard` : "Gagal menyalin ke clipboard");
  });
  $("#pdfLink").addEventListener("click", e => {
    if (!S.monthRows) { e.preventDefault(); setStatus("Tidak ada data untuk diekspor"); return; }
    setStatus("Membuat PDF…");
  });
  // pintasan & pengaman
  document.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      if (currentTab() === "rekap" && !$("#saveBtn").disabled) save().catch(err => setStatus(err.message));
    }
  });
  window.addEventListener("beforeunload", e => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });

  // tema
  const apply = t => { document.documentElement.dataset.theme = t; };
  try { apply(localStorage.getItem("buktitf-theme") || "dark"); } catch { apply("dark"); }
  on($("#themeBtn"), "click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    apply(next);
    try { localStorage.setItem("buktitf-theme", next); } catch { /* abaikan */ }
  });
}

async function init() {
  wire();
  $("#tanggal").value = todayISO();
  addExpense();
  clearPreview(); renderReceipt();
  const d = new Date(); S.hist = { y: d.getFullYear(), m: d.getMonth() + 1 };
  try {
    const rec = await fetchRecord(todayISO());
    if (rec) loadRecord(rec); else await evaluate(true);
  } catch (e) { setStatus(e.message); }
  S.dirty = false; updateState();
}
init();
})();
