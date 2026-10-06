const dashEscape = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[character]);

function displayTime(value, options = { hour: 'numeric', minute: '2-digit' }) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? '—' : date.toLocaleTimeString([], options);
}

function setStatus(id, value, good) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
  const orb = document.getElementById(id.replace('-state', '-orb'));
  if (orb) orb.classList.toggle('active', Boolean(good));
}

function activityMarkup(item) {
  const spam = item.prediction === 'spam';
  const preview = String(item.message || '').slice(0, 88);
  const time = item.created_at ? new Date(item.created_at) : null;
  return `<article class="activity-row ${spam ? 'is-spam' : 'is-ham'}">
    <div class="activity-time">${dashEscape(displayTime(item.created_at))}<small>${time && !Number.isNaN(time.valueOf()) ? dashEscape(time.toLocaleDateString()) : ''}</small></div>
    <div class="activity-copy"><span class="activity-sender">${dashEscape(item.sender || 'Unknown sender')}</span><p>${dashEscape(preview || 'Message preview unavailable')}</p></div>
    <div class="activity-result"><span class="table-prediction ${spam ? 'spam' : 'ham'}">${spam ? 'SPAM' : 'SAFE'}</span><strong>${(Number(item.confidence || 0) * 100).toFixed(0)}% confidence</strong><small class="risk-label ${spam ? 'risk-high' : 'risk-low'}">${dashEscape(item.risk_level || (spam ? 'HIGH' : 'LOW'))} RISK</small></div>
  </article>`;
}

async function refreshProtectionDashboard() {
  const errors = [];
  const [statsResult, statusResult, historyResult] = await Promise.allSettled([
    fetch('/api/stats').then(async (response) => ({ response, data: await response.json() })),
    fetch('/api/protection-status').then(async (response) => ({ response, data: await response.json() })),
    fetch('/api/history').then(async (response) => ({ response, data: await response.json() }))
  ]);

  if (statsResult.status === 'fulfilled' && statsResult.value.response.ok) {
    const stats = statsResult.value.data;
    document.getElementById('stat-total-val').textContent = Number(stats.total_messages ?? stats.total ?? 0).toLocaleString();
    document.getElementById('stat-spam-val').textContent = Number(stats.spam_messages ?? stats.spam ?? 0).toLocaleString();
    document.getElementById('stat-ham-val').textContent = Number(stats.ham_messages ?? stats.ham ?? 0).toLocaleString();
    document.getElementById('stat-high-risk-val').textContent = Number(stats.high_risk_messages ?? 0).toLocaleString();
  } else {
    errors.push(statsResult.status === 'fulfilled' ? statsResult.value.data.error : 'Statistics could not be reached.');
  }

  if (statusResult.status === 'fulfilled' && statusResult.value.response.ok) {
    const status = statusResult.value.data;
    const active = Boolean(status.protection_active);
    const protection = document.getElementById('protection-state');
    if (protection) protection.textContent = active ? 'Active' : 'Inactive';
    const orb = document.getElementById('protection-orb');
    if (orb) orb.classList.toggle('active', active);
    setStatus('phone-state', status.phone_connected ? 'Connected' : 'Not connected', status.phone_connected);
    setStatus('monitoring-state', status.monitoring_active ? 'Active' : 'Inactive', status.monitoring_active);
  } else {
    errors.push(statusResult.status === 'fulfilled' ? statusResult.value.data.error : 'Phone status could not be reached.');
  }

  if (historyResult.status === 'fulfilled' && historyResult.value.response.ok) {
    const history = historyResult.value.data;
    const activity = document.getElementById('recent-activity');
    if (activity) {
      activity.innerHTML = history.length
        ? history.slice(0, 6).map(activityMarkup).join('')
        : '<div class="activity-empty">Waiting for the first phone classification…</div>';
    }
    const lastScan = document.getElementById('last-scan-time');
    if (lastScan) lastScan.textContent = history.length ? displayTime(history[0].created_at, { hour: 'numeric', minute: '2-digit', second: '2-digit' }) : 'No scans yet';
  } else {
    errors.push(historyResult.status === 'fulfilled' ? historyResult.value.data.error : 'Recent SMS activity could not be loaded.');
  }

  const updated = document.getElementById('updated-at');
  if (updated) updated.textContent = displayTime(new Date().toISOString(), { hour: 'numeric', minute: '2-digit', second: '2-digit' });
  const error = document.getElementById('dashboard-error');
  if (error) error.textContent = [...new Set(errors.filter(Boolean))].join(' ');
}

refreshProtectionDashboard();
window.setInterval(refreshProtectionDashboard, 15000);
