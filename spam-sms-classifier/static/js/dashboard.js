/**
 * dashboard.js — SpamGuard Real-Time Dashboard
 * Connects to real Flask backend APIs: /api/stats, /api/protection-status, /api/history
 */

let dashboardDoughnutChart = null;

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

function formatRelativeTime(isoString) {
  if (!isoString) return '—';
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return '—';
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);
    if (diffSec < 60) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return '—';
  }
}

async function loadDashboard() {
  try {
    const [statsRes, statusRes, historyRes] = await Promise.all([
      fetch('/api/stats').then(r => r.ok ? r.json() : null),
      fetch('/api/protection-status').then(r => r.ok ? r.json() : null),
      fetch('/api/history?limit=8').then(r => r.ok ? r.json() : [])
    ]);

    // 1. Stats Cards
    if (statsRes) {
      const total = Number(statsRes.total_messages ?? statsRes.total ?? 0);
      const spam = Number(statsRes.spam_messages ?? statsRes.spam ?? 0);
      const safe = Number(statsRes.ham_messages ?? statsRes.ham ?? 0);
      const highRisk = Number(statsRes.high_risk_messages ?? 0);

      const elTotal = document.getElementById('stat-total');
      const elSpam = document.getElementById('stat-spam');
      const elSafe = document.getElementById('stat-safe');
      const elHigh = document.getElementById('stat-high-risk');

      if (elTotal) elTotal.textContent = total.toLocaleString();
      if (elSpam) elSpam.textContent = spam.toLocaleString();
      if (elSafe) elSafe.textContent = safe.toLocaleString();
      if (elHigh) elHigh.textContent = highRisk.toLocaleString();

      // Doughnut Chart
      const chartCanvas = document.getElementById('doughnut-chart');
      const chartEmpty = document.getElementById('chart-empty');

      if (chartCanvas && window.Chart) {
        if (total === 0) {
          chartCanvas.style.display = 'none';
          if (chartEmpty) chartEmpty.style.display = 'block';
        } else {
          chartCanvas.style.display = 'block';
          if (chartEmpty) chartEmpty.style.display = 'none';

          if (dashboardDoughnutChart) {
            dashboardDoughnutChart.data.datasets[0].data = [spam, safe];
            dashboardDoughnutChart.update();
          } else {
            dashboardDoughnutChart = new Chart(chartCanvas, {
              type: 'doughnut',
              data: {
                labels: ['Spam', 'Safe'],
                datasets: [{
                  data: [spam, safe],
                  backgroundColor: ['#ef4444', '#10b981'],
                  borderColor: '#0f172a',
                  borderWidth: 3,
                  hoverOffset: 4
                }]
              },
              options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                plugins: {
                  legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', font: { family: 'Outfit, sans-serif', size: 12 }, padding: 12 }
                  },
                  tooltip: {
                    callbacks: {
                      label: (ctx) => ` ${ctx.label}: ${ctx.raw} (${total ? ((ctx.raw / total) * 100).toFixed(1) : 0}%)`
                    }
                  }
                }
              }
            });
          }
        }
      }
    }

    // 2. Protection / Device Status
    if (statusRes) {
      const isConnected = Boolean(statusRes.phone_connected);
      const isMonitoring = Boolean(statusRes.monitoring_active);
      const isMlActive = statusRes.ml_active !== false;
      const isProtected = Boolean(statusRes.protection_active);

      const elBadge = document.getElementById('protection-badge');
      if (elBadge) {
        if (isProtected) {
          elBadge.className = 'protection-badge active';
          elBadge.innerHTML = '<span class="pulse-dot"></span> PROTECTION ACTIVE';
        } else if (isConnected) {
          elBadge.className = 'protection-badge warning';
          elBadge.innerHTML = '<span class="pulse-dot" style="background:var(--orange)"></span> MONITORING PAUSED';
        } else {
          elBadge.className = 'protection-badge inactive';
          elBadge.innerHTML = '<span class="pulse-dot" style="background:var(--text-muted)"></span> WAITING FOR DEVICE';
        }
      }

      const elPhone = document.getElementById('phone-status');
      if (elPhone) {
        elPhone.innerHTML = isConnected
          ? '<span style="color:var(--green)">● Connected</span>'
          : '<span style="color:var(--text-muted)">○ Not Connected</span>';
      }

      const elMonitoring = document.getElementById('monitoring-status');
      if (elMonitoring) {
        elMonitoring.innerHTML = isMonitoring
          ? '<span style="color:var(--green)">● Active</span>'
          : '<span style="color:var(--text-muted)">○ Inactive</span>';
      }

      const elMl = document.getElementById('ml-status');
      if (elMl) {
        elMl.innerHTML = isMlActive
          ? '<span style="color:var(--blue-bright)">● Ready (SVM)</span>'
          : '<span style="color:var(--red)">○ Offline</span>';
      }
    }

    // 3. Recent Activity List
    const activityContainer = document.getElementById('recent-activity');
    if (activityContainer) {
      const items = Array.isArray(historyRes) ? historyRes : [];
      if (items.length === 0) {
        activityContainer.innerHTML = `
          <div class="sms-empty" style="padding:28px 16px;text-align:center">
            <div style="font-size:1.8rem;margin-bottom:8px">📥</div>
            <strong style="color:var(--text)">No SMS Activity Yet</strong>
            <p style="font-size:0.85rem;color:var(--text-muted);margin-top:4px">
              Messages received on your connected Android phone will appear here in real time.
            </p>
          </div>
        `;
      } else {
        activityContainer.innerHTML = items.map(item => {
          const isSpam = item.prediction === 'spam';
          const sender = escapeHtml(item.sender || 'Unknown');
          const preview = escapeHtml(item.message || '');
          const time = formatRelativeTime(item.created_at);
          const conf = (Number(item.confidence || 0) * 100).toFixed(0);
          const risk = escapeHtml(item.risk_level || (isSpam ? 'HIGH' : 'LOW'));
          const badgeClass = isSpam ? 'badge-spam' : 'badge-safe';
          const riskClass = risk === 'HIGH' ? 'risk-high' : 'risk-low';

          return `
            <div class="activity-item" onclick="window.location.href='/inbox'" style="cursor:pointer">
              <div class="activity-icon ${isSpam ? 'spam-icon' : 'safe-icon'}">
                ${isSpam ? '🚨' : '🛡️'}
              </div>
              <div class="activity-content">
                <div class="activity-top">
                  <span class="activity-sender">${sender}</span>
                  <span class="activity-time">${time}</span>
                </div>
                <div class="activity-preview">${preview}</div>
              </div>
              <div class="activity-meta">
                <span class="badge ${badgeClass}">${isSpam ? 'SPAM' : 'SAFE'}</span>
                <span class="activity-risk ${riskClass}">${risk} RISK (${conf}%)</span>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    const errEl = document.getElementById('activity-error');
    if (errEl) errEl.textContent = '';

  } catch (err) {
    console.error('Dashboard refresh error:', err);
    const errEl = document.getElementById('activity-error');
    if (errEl) errEl.textContent = 'Unable to reach SpamGuard server. Retrying...';
  }
}

// Initial load and periodic polling every 8 seconds
loadDashboard();
setInterval(loadDashboard, 8000);
