/* ============================================================
   BTC LSTM Dashboard — chart_logic.js
   ============================================================ */

   'use strict';

   /* ----------------------------------------------------------
      CONFIG
      ---------------------------------------------------------- */
   const C = {
       orange:    '#f7931a',
       orangeFill:'rgba(247,147,26,0.08)',
       green:     '#22c55e',
       purple:    '#a78bfa',
       slate:     '#94a3b8',
       grid:      'rgba(255,255,255,0.05)',
       tickColor: 'rgba(255,255,255,0.22)',
       font:      "'Space Mono', monospace",
   };
   
   /* ----------------------------------------------------------
      CHART DEFAULTS
      ---------------------------------------------------------- */
   const defaultScales = () => ({
       x: {
           ticks: {
               color: C.tickColor,
               font: { size: 9, family: C.font },
               maxTicksLimit: 8,
               maxRotation: 0,
           },
           grid:   { color: C.grid },
           border: { color: 'transparent' },
       },
       y: {
           ticks: {
               color: C.tickColor,
               font: { size: 9, family: C.font },
               callback: v => '$' + (v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v),
           },
           grid:   { color: C.grid },
           border: { color: 'transparent' },
       },
   });
   
   const defaultPlugins = {
       legend: { display: false },
       tooltip: {
           backgroundColor: 'rgba(13,17,23,0.95)',
           titleColor:      '#f7931a',
           bodyColor:       'rgba(255,255,255,0.7)',
           borderColor:     'rgba(247,147,26,0.2)',
           borderWidth:     1,
           padding:         10,
           titleFont:       { family: "'Space Mono', monospace", size: 10 },
           bodyFont:        { family: "'Outfit', sans-serif", size: 11 },
           callbacks: {
               label: ctx => ' $' + Number(ctx.parsed.y).toLocaleString('en-US', {
                   minimumFractionDigits: 2,
                   maximumFractionDigits: 2,
               }),
           },
       },
   };
   
   /* ----------------------------------------------------------
      RENDER DASHBOARD CHART
      ---------------------------------------------------------- */
   function renderDashboardChart(labels, actualData) {
       const canvas = document.getElementById('chartDashboard');
       if (!canvas) return;
       new Chart(canvas, {
           type: 'line',
           data: {
               labels,
               datasets: [{
                   label:                     'Harga BTC ($)',
                   data:                      actualData,
                   borderColor:               C.orange,
                   backgroundColor:           C.orangeFill,
                   fill:                      true,
                   tension:                   0.4,
                   pointRadius:               0,
                   pointHoverRadius:          4,
                   pointHoverBackgroundColor: C.orange,
                   borderWidth:               1.5,
               }],
           },
           options: {
               responsive: true, maintainAspectRatio: false,
               animation: { duration: 600, easing: 'easeOutQuart' },
               interaction: { mode: 'index', intersect: false },
               plugins: defaultPlugins,
               scales:  defaultScales(),
           },
       });
   }
   
   /* ----------------------------------------------------------
      RENDER ANALISIS CHART
      ---------------------------------------------------------- */
   const _chartInstances = {};
   
   function renderAnalisisChart(labels, actualData, predBiv, predMult) {
       const canvas = document.getElementById('chartAnalisis');
       if (!canvas) return;
       if (_chartInstances['chartAnalisis']) _chartInstances['chartAnalisis'].destroy();
   
       _chartInstances['chartAnalisis'] = new Chart(canvas, {
           type: 'line',
           data: {
               labels,
               datasets: [
                   { label: 'Aktual',       data: actualData, borderColor: C.slate,  fill: false, tension: 0.4, pointRadius: 0, pointHoverRadius: 4, borderWidth: 1.8 },
                   { label: 'Bivariate',    data: predBiv,    borderColor: C.orange, borderDash: [5,4], fill: false, tension: 0.4, pointRadius: 0, pointHoverRadius: 4, borderWidth: 1.5 },
                   { label: 'Multivariate', data: predMult,   borderColor: C.purple, borderDash: [3,3], fill: false, tension: 0.4, pointRadius: 0, pointHoverRadius: 4, borderWidth: 1.5 },
               ],
           },
           options: {
               responsive: true, maintainAspectRatio: false,
               animation: { duration: 600, easing: 'easeOutQuart' },
               interaction: { mode: 'index', intersect: false },
               plugins: defaultPlugins,
               scales:  defaultScales(),
           },
       });
   }
   
   /* ----------------------------------------------------------
      TOGGLE DATASET
      ---------------------------------------------------------- */
   function toggleDataset(chartId, datasetIndex) {
       const chart = _chartInstances[chartId];
       if (!chart) return;
       const meta = chart.getDatasetMeta(datasetIndex);
       meta.hidden = !meta.hidden;
       chart.update();
       const btnIds = ['tog-aktual', 'tog-biv', 'tog-mult'];
       const btn = document.getElementById(btnIds[datasetIndex]);
       if (btn) btn.classList.toggle('active', !meta.hidden);
   }
   
   /* ----------------------------------------------------------
      RENDER PREDIKSI CHART
      ---------------------------------------------------------- */
   function renderPrediksiChart(labels, actualData, predData) {
       const canvas = document.getElementById('chartPrediksi');
       if (!canvas) return;
       new Chart(canvas, {
           type: 'line',
           data: {
               labels,
               datasets: [
                   { label: 'Harga Aktual', data: actualData, borderColor: C.slate, fill: false, tension: 0.4, pointRadius: 0, pointHoverRadius: 4, borderWidth: 1.5 },
                   { label: 'Prediksi LSTM', data: predData,  borderColor: C.green, borderDash: [5,4], fill: false, tension: 0.4, pointRadius: 0, pointHoverRadius: 4, borderWidth: 1.5 },
               ],
           },
           options: {
               responsive: true, maintainAspectRatio: false,
               animation: { duration: 600, easing: 'easeOutQuart' },
               interaction: { mode: 'index', intersect: false },
               plugins: defaultPlugins,
               scales:  defaultScales(),
           },
       });
   }
   
   /* ----------------------------------------------------------
      NAVIGASI — hash-based
      ---------------------------------------------------------- */
   const PAGE_META = {
       dashboard: { title: 'Dashboard Utama',    sub: 'Ringkasan prediksi & trend BTC' },
       prediksi:  { title: 'Prediksi Kustom',    sub: 'Masukkan tanggal & jam di masa depan untuk estimasi harga' },
       analisis:  { title: 'Analisis Ketepatan', sub: 'Backtesting & evaluasi performa model LSTM' },
   };
   
   function handleNavigation() {
       const hash = window.location.hash.substring(1) || 'dashboard';
       document.querySelectorAll('.section').forEach(s => s.classList.add('d-none'));
       const target = document.getElementById('container-' + hash);
       if (target) target.classList.remove('d-none');
       document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
       const activeLink = document.getElementById('link-' + hash);
       if (activeLink) activeLink.classList.add('active');
       const meta = PAGE_META[hash] || PAGE_META.dashboard;
       const titleEl = document.getElementById('page-title');
       const subEl   = document.getElementById('page-sub');
       if (titleEl) titleEl.textContent = meta.title;
       if (subEl)   subEl.textContent   = meta.sub;
   }
   
   /* ----------------------------------------------------------
      MODE TOGGLE
      ---------------------------------------------------------- */
   let _currentMode = 'bivariate';
   
   function setMode(mode) {
       _currentMode = mode;
       document.getElementById('btn-mode-biv').classList.toggle('active', mode === 'bivariate');
       document.getElementById('btn-mode-mult').classList.toggle('active', mode === 'multivariate');
       const resultBox = document.getElementById('hasil-prediksi-kustom');
       if (resultBox) resultBox.classList.add('d-none');
       const errBox = document.getElementById('result-error');
       if (errBox) errBox.classList.add('d-none');
   }
   
   /* ----------------------------------------------------------
      DATETIME PICKER MIN (Prediksi Kustom)
      ---------------------------------------------------------- */
   function initDatetimePicker() {
       const picker = document.getElementById('input_datetime');
       if (!picker) return;
       function getMinNow() {
           const now = new Date(Date.now() + 60000);
           const pad = n => String(n).padStart(2, '0');
           return `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
       }
       picker.min = getMinNow();
       setInterval(() => {
           picker.min = getMinNow();
           if (picker.value && picker.value < picker.min) picker.value = '';
       }, 60000);
   }
   
   /* ----------------------------------------------------------
      PREDIKSI KUSTOM
      ---------------------------------------------------------- */
   async function getCustomPrediction() {
       const picker    = document.getElementById('input_datetime');
       const resultBox = document.getElementById('hasil-prediksi-kustom');
       const valBox    = document.getElementById('val_prediksi_kustom');
       const noteBox   = document.getElementById('result-target-note');
       const labelBox  = document.getElementById('result-mode-label');
       const errBox    = document.getElementById('result-error');
       if (!picker || !resultBox || !valBox) return;
   
       const dtValue = picker.value;
       if (!dtValue) { showError(errBox, 'Silakan pilih tanggal dan jam terlebih dahulu.'); return; }
       if (new Date(dtValue) <= new Date()) { showError(errBox, 'Waktu yang dipilih sudah lewat. Pilih waktu di masa depan.'); return; }
   
       if (errBox) { errBox.classList.add('d-none'); errBox.textContent = ''; }
       resultBox.classList.remove('d-none');
       valBox.textContent   = '...memproses...';
       valBox.style.opacity = '0.4';
       if (labelBox) labelBox.textContent = `Estimasi Harga LSTM · ${_currentMode === 'bivariate' ? 'Bivariate' : 'Multivariate'}`;
   
       try {
           const res  = await fetch(`/api/predict?datetime=${encodeURIComponent(dtValue)}&mode=${_currentMode}`);
           const data = await res.json();
           if (!res.ok) { resultBox.classList.add('d-none'); showError(errBox, data.error || 'Prediksi gagal. Coba lagi.'); return; }
   
           const price = Number(data.predicted_price);
           valBox.textContent   = '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
           valBox.style.opacity = '1';
           valBox.style.color   = _currentMode === 'bivariate' ? C.orange : C.purple;
           if (noteBox) {
               const d = new Date(dtValue);
               noteBox.textContent = `Target: ${d.toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' })} · ${_currentMode === 'bivariate' ? 'BTC + Emas' : '6 Aset Logam'}`;
           }
       } catch (e) {
           resultBox.classList.add('d-none');
           showError(errBox, 'Gagal menghubungi server. Periksa koneksi Anda.');
       }
   }
   
   function showError(el, msg) {
       if (!el) return;
       el.textContent = '⚠ ' + msg;
       el.classList.remove('d-none');
   }
   
   /* ----------------------------------------------------------
      INTERVAL PILLS
      ---------------------------------------------------------- */
   function initIntervalPills() {
       const pills         = document.querySelectorAll('.ipill');
       const inputDate     = document.getElementById('input-target-date');
       const inputDatetime = document.getElementById('input-target-datetime');
       const labelInput    = document.getElementById('label-target-input');
       const hintBox       = document.getElementById('intraday-hint');
   
       // Terapkan mode awal dari pill yang sudah active
       const activePill = document.querySelector('.ipill.ipill-active');
       if (activePill) _applyIntervalMode(activePill.dataset.mode, inputDate, inputDatetime, labelInput, hintBox);
   
       pills.forEach(label => {
           label.addEventListener('click', () => {
               pills.forEach(l => l.classList.remove('ipill-active'));
               label.classList.add('ipill-active');
               _applyIntervalMode(label.dataset.mode, inputDate, inputDatetime, labelInput, hintBox);
           });
       });
   }
   
   function _applyIntervalMode(mode, inputDate, inputDatetime, labelInput, hintBox) {
       if (!inputDate || !inputDatetime) return;
       if (mode === 'intraday') {
           inputDate.classList.add('d-none');
           inputDate.removeAttribute('name');
           inputDatetime.classList.remove('d-none');
           inputDatetime.setAttribute('name', 'target_datetime');
           if (labelInput) labelInput.textContent = 'Waktu Akhir Analisis (tanggal & jam)';
           if (hintBox)    hintBox.classList.remove('d-none');
           _setDatetimeMax(inputDatetime);
       } else {
           inputDatetime.classList.add('d-none');
           inputDatetime.removeAttribute('name');
           inputDate.classList.remove('d-none');
           inputDate.setAttribute('name', 'target_date');
           if (labelInput) labelInput.textContent = 'Tanggal Akhir (tidak bisa melebihi hari ini)';
           if (hintBox)    hintBox.classList.add('d-none');
       }
   }
   
   function _setDatetimeMax(el) {
       if (!el) return;
       const now = new Date();
       const pad = n => String(n).padStart(2, '0');
       el.max = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
   }
   
   /* ----------------------------------------------------------
      FORM ANALISIS — pisah datetime → target_date + target_time
      ---------------------------------------------------------- */
   function initAnalysisForm() {
       const form = document.getElementById('form-backtesting');
       if (!form) return;
   
       form.addEventListener('submit', function () {
           const inputDatetime = document.getElementById('input-target-datetime');
           const inputDate     = document.getElementById('input-target-date');
   
           // Jaga agar history_range selalu ikut dikirim
           const hrInput = form.querySelector('input[name="history_range"]');
           if (hrInput) hrInput.setAttribute('name', 'history_range');
   
           if (inputDatetime && !inputDatetime.classList.contains('d-none') && inputDatetime.value) {
               // Mode intraday: pecah datetime → date + time
               const [datePart, timePart] = inputDatetime.value.split('T');
   
               // Hapus name dari date input agar tidak bentrok
               if (inputDate) inputDate.removeAttribute('name');
   
               // Hidden field: target_date
               let hiddenDate = form.querySelector('#target_date_intraday');
               if (!hiddenDate) {
                   hiddenDate      = document.createElement('input');
                   hiddenDate.type = 'hidden';
                   hiddenDate.name = 'target_date';
                   hiddenDate.id   = 'target_date_intraday';
                   form.appendChild(hiddenDate);
               }
               hiddenDate.value = datePart;
   
               // Hidden field: target_time  ← server membaca parameter ini
               let hiddenTime = form.querySelector('input[name="target_time"]');
               if (!hiddenTime) {
                   hiddenTime      = document.createElement('input');
                   hiddenTime.type = 'hidden';
                   hiddenTime.name = 'target_time';
                   form.appendChild(hiddenTime);
               }
               hiddenTime.value = timePart || '23:59';
   
           } else {
               // Mode harian: pastikan input date punya name yang benar
               if (inputDate) inputDate.setAttribute('name', 'target_date');
           }
       });
   }
   
   /* ----------------------------------------------------------
      INIT — dipanggil dari index.html
      ---------------------------------------------------------- */
   function initApp(histDates, histActuals, histPreds, histPredsMult, prediksiVal, prediksiMult) {
       window._PREDIKSI_BIV  = prediksiVal;
       window._PREDIKSI_MULT = prediksiMult;
   
       window.addEventListener('hashchange', handleNavigation);
   
       window.addEventListener('load', () => {
           const params    = new URLSearchParams(window.location.search);
           const hasParams = params.has('history_range') || params.has('target_date') || params.has('interval');
   
           // PERBAIKAN BUG 2: set hash DULU sebelum handleNavigation()
           if (hasParams && params.get('section') === 'analisis') {
               window.location.hash = '#analisis';
           }
   
           handleNavigation();
           renderAllCharts(histDates, histActuals, histPreds, histPredsMult);
           initDatetimePicker();
           initIntervalPills();
           initAnalysisForm();
       });
   }
   
   function renderAllCharts(histDates, histActuals, histPreds, histPredsMult) {
       renderDashboardChart(histDates, histActuals);
       renderAnalisisChart(histDates, histActuals, histPreds, histPredsMult);
       renderPrediksiChart(histDates, histActuals, histPreds);
   }