const analyticsCharts = {};
const analyticsPalette = { spam: '#ff7864', ham: '#75d5ad', high: '#ff7864', low: '#b8e66b' };

function updateChart(id, config) {
  if (!window.Chart) return;
  const canvas = document.getElementById(id);
  if (!canvas) return;
  if (analyticsCharts[id]) {
    analyticsCharts[id].data = config.data;
    analyticsCharts[id].options = config.options;
    analyticsCharts[id].update();
  } else {
    analyticsCharts[id] = new Chart(canvas, config);
  }
}

async function refreshAnalytics() {
  try {
    const [statsResponse, analyticsResponse] = await Promise.all([fetch('/api/stats'), fetch('/api/analytics')]);
    const [stats, analytics] = await Promise.all([statsResponse.json(), analyticsResponse.json()]);
    if (!statsResponse.ok) throw new Error(stats.error || 'Dashboard totals could not be loaded.');
    if (!analyticsResponse.ok) throw new Error(analytics.error || 'Analytics could not be loaded.');

    const total = Number(stats.total_messages ?? stats.total ?? 0);
    const spam = Number(stats.spam_messages ?? stats.spam ?? 0);
    const ham = Number(stats.ham_messages ?? stats.ham ?? 0);
    const high = Number(stats.high_risk_messages ?? 0);
    const rate = total ? spam / total * 100 : 0;
    const confidence = Number(analytics.average_confidence || 0) * 100;
    document.getElementById('analytics-total').textContent = total.toLocaleString();
    document.getElementById('analytics-rate').textContent = `${rate.toFixed(1)}%`;
    document.getElementById('analytics-high-risk').textContent = high.toLocaleString();
    document.getElementById('analytics-confidence').textContent = `${confidence.toFixed(1)}%`;
    document.getElementById('confidence-average').textContent = `${confidence.toFixed(1)}%`;
    document.getElementById('confidence-meter').style.width = `${Math.min(100, confidence)}%`;

    const baseOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#b6c4b7' } } } };
    updateChart('spam-ham-chart', {
      type: 'doughnut',
      data: { labels: ['Spam', 'Safe'], datasets: [{ data: [spam, ham], backgroundColor: [analyticsPalette.spam, analyticsPalette.ham], borderWidth: 0 }] },
      options: { ...baseOptions, cutout: '68%' }
    });
    const daily = Array.isArray(analytics.daily) ? analytics.daily : [];
    updateChart('daily-chart', {
      type: 'line',
      data: { labels: daily.map((entry) => entry.day), datasets: [
        { label: 'Spam', data: daily.map((entry) => entry.spam), borderColor: analyticsPalette.spam, backgroundColor: `${analyticsPalette.spam}22`, fill: true, tension: 0.32 },
        { label: 'Safe', data: daily.map((entry) => entry.ham), borderColor: analyticsPalette.ham, backgroundColor: `${analyticsPalette.ham}22`, fill: true, tension: 0.32 }
      ] },
      options: { ...baseOptions, scales: { x: { ticks: { color: '#9baa9c' }, grid: { color: '#26342a' } }, y: { beginAtZero: true, ticks: { precision: 0, color: '#9baa9c' }, grid: { color: '#26342a' } } } }
    });
    const risk = analytics.risk_levels || {};
    updateChart('risk-chart', {
      type: 'bar',
      data: { labels: ['High risk', 'Low risk'], datasets: [{ data: [Number(risk.HIGH || 0), Number(risk.LOW || 0)], backgroundColor: [analyticsPalette.high, analyticsPalette.low], borderRadius: 6 }] },
      options: { ...baseOptions, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: '#9baa9c' }, grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0, color: '#9baa9c' }, grid: { color: '#26342a' } } } }
    });
    document.getElementById('analytics-error').textContent = '';
  } catch (error) {
    document.getElementById('analytics-error').textContent = error.message;
  }
}

refreshAnalytics();
window.setInterval(refreshAnalytics, 20000);
