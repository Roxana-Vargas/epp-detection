/* Render de gráficos con Chart.js */
const Charts = (() => {
  let trend = null, klass = null;

  const baseGrid = { color: 'rgba(255,255,255,.05)' };
  const baseTicks = { color: '#94a3b8', font: { family: 'Inter', size: 11 } };

  Chart.defaults.font.family = 'Inter';
  Chart.defaults.color = '#94a3b8';

  function renderTrend(ts) {
    const ctx = document.getElementById('chart-trend');
    const grad = ctx.getContext('2d').createLinearGradient(0, 0, 0, 240);
    grad.addColorStop(0, 'rgba(16,185,129,.35)');
    grad.addColorStop(1, 'rgba(16,185,129,0)');

    const data = {
      labels: ts.labels.length ? ts.labels : ['—'],
      datasets: [
        { label: 'Cumplen', data: ts.cumplen, borderColor: '#10b981', backgroundColor: grad,
          fill: true, tension: .35, borderWidth: 2, pointRadius: 3, pointBackgroundColor: '#10b981' },
        { label: 'Violaciones', data: ts.violan, borderColor: '#ef4444', backgroundColor: 'transparent',
          fill: false, tension: .35, borderWidth: 2, pointRadius: 3, pointBackgroundColor: '#ef4444' },
      ],
    };
    const opts = {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#cbd5e1', usePointStyle: true, boxWidth: 8 } } },
      scales: {
        x: { grid: baseGrid, ticks: baseTicks },
        y: { grid: baseGrid, ticks: { ...baseTicks, precision: 0 }, beginAtZero: true },
      },
    };
    if (trend) { trend.data = data; trend.update(); }
    else trend = new Chart(ctx, { type: 'line', data, options: opts });
  }

  function renderClass(bc) {
    const empty = document.getElementById('class-empty');
    const canvas = document.getElementById('chart-class');
    if (!bc.labels.length) {
      canvas.classList.add('hidden'); empty.classList.remove('hidden');
      if (klass) { klass.destroy(); klass = null; }
      return;
    }
    canvas.classList.remove('hidden'); empty.classList.add('hidden');
    const palette = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#a855f7', '#ec4899', '#14b8a6'];
    const data = {
      labels: bc.labels,
      datasets: [{ data: bc.values, backgroundColor: bc.labels.map((_, i) => palette[i % palette.length]),
        borderColor: '#0b1220', borderWidth: 3, hoverOffset: 6 }],
    };
    const opts = {
      responsive: true, maintainAspectRatio: false, cutout: '62%',
      plugins: { legend: { position: 'bottom', labels: { color: '#cbd5e1', usePointStyle: true, boxWidth: 8, padding: 12 } } },
    };
    if (klass) { klass.data = data; klass.update(); }
    else klass = new Chart(canvas, { type: 'doughnut', data, options: opts });
  }

  return { renderTrend, renderClass };
})();
