async function loadDashboardStats() {
  try {
    const [statsResponse, historyResponse] = await Promise.all([
      fetch('/api/stats'),
      fetch('/api/history')
    ]);

    const statsData = await statsResponse.json();
    const historyData = await historyResponse.json();

    if (!statsResponse.ok || !statsData) throw new Error(statsData?.error || 'Unable to load dashboard stats');
    if (!historyResponse.ok) throw new Error(historyData?.error || 'Unable to load recent predictions');

    const recentItems = Array.isArray(historyData) ? historyData : (Array.isArray(historyData.history) ? historyData.history : []);
    const data = Object.assign({}, statsData, { recent: recentItems.slice(0, 6) });

    const total = Number(data.total || 0);
    const spam = Number(data.spam || 0);
    const ham = Number(data.ham || 0);
    const spamPct = total ? ((spam / total) * 100).toFixed(1) : '0.0';

    document.getElementById('stat-total-val').textContent = total;
    document.getElementById('stat-spam-val').textContent = spam;
    document.getElementById('stat-ham-val').textContent = ham;
    document.getElementById('stat-pct-val').textContent = `${spamPct}%`;

    const recentBody = document.getElementById('recent-activity-body');
    if (recentBody) {
      const items = Array.isArray(data.recent) ? data.recent : [];
      if (!items.length) {
        recentBody.innerHTML = '<tr><td colspan="5">No recent predictions yet.</td></tr>';
        return;
      }

      recentBody.innerHTML = items.slice(0, 6).map((item) => {
        const message = item.message || item.text || '';
        const text = message ? message.slice(0, 28) + (message.length > 28 ? '...' : '') : 'N/A';
        const isSpam = item.prediction === 'spam';
        const prediction = isSpam ? 'SPAM' : 'HAM';
        const confidence = (Number(item.confidence || 0) * 100).toFixed(1);
        const createdAt = item.created_at ? new Date(item.created_at).toLocaleString() : 'N/A';
        const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
          '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[character]);
        return `<tr><td>${item.id}</td><td>${escapeHtml(text)}</td><td><span class="table-prediction ${isSpam ? 'spam' : 'ham'}">${prediction}</span></td><td>${confidence}%</td><td>${escapeHtml(createdAt)}</td></tr>`;
      }).join('');
    }

    const chartCanvas = document.getElementById('donut-chart');
    if (chartCanvas && window.Chart) {
      const labels = ['Spam', 'Ham'];
      const values = [spam, ham];
      const chart = new Chart(chartCanvas, {
        type: 'doughnut',
        data: {
          labels,
          datasets: [{
            data: values,
            backgroundColor: ['#ff7864', '#75d5ad'],
            borderWidth: 0,
            hoverOffset: 6
          }]
        },
        options: {
          cutout: '65%',
          plugins: {
            legend: { display: false },
            tooltip: { enabled: true }
          }
        }
      });

      const chartCenter = document.getElementById('chart-center-text');
      if (chartCenter) {
        chartCenter.textContent = `${spamPct}%`;
      }

      chartCanvas.dataset.chart = 'loaded';
    }
  } catch (error) {
    console.error('Dashboard error:', error);
    const recentBody = document.getElementById('recent-activity-body');
    if (recentBody) {
      recentBody.innerHTML = '<tr><td colspan="5">Unable to load dashboard data.</td></tr>';
    }
  }
}

loadDashboardStats();
