async function refreshProtectionStatus() {
  try {
    const [statusResponse, historyResponse] = await Promise.all([
      fetch('/api/protection-status'),
      fetch('/api/history')
    ]);
    const status = await statusResponse.json();
    const history = await historyResponse.json();
    if (!statusResponse.ok) throw new Error(status.error || 'Protection status could not be loaded.');

    const values = {
      'live-phone-status': status.phone_connected ? 'Connected' : 'Not connected',
      'live-sms-status': status.monitoring_active ? 'Active' : 'Inactive',
      'live-ml-status': status.ml_active ? 'Active' : 'Unavailable',
      'settings-phone': status.phone_connected ? 'Connected' : 'Not connected',
      'settings-monitoring': status.monitoring_active ? 'Active' : 'Inactive',
      'settings-ml': status.ml_active ? 'Active' : 'Unavailable'
    };
    Object.entries(values).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) element.textContent = value;
    });

    const seen = document.getElementById('live-phone-seen');
    if (seen) seen.textContent = status.last_seen ? `Last phone heartbeat ${new Date(status.last_seen).toLocaleString()}` : 'No phone heartbeat received';

    const cardPhone = document.getElementById('card-phone');
    const cardSms   = document.getElementById('card-sms');
    const cardMl    = document.getElementById('card-ml');

    if (cardPhone) cardPhone.classList.toggle('active', Boolean(status.phone_connected));
    if (cardSms)   cardSms.classList.toggle('active', Boolean(status.monitoring_active));
    if (cardMl)    cardMl.classList.toggle('active', Boolean(status.ml_active));

    [['live-phone-orb', status.phone_connected], ['live-sms-orb', status.monitoring_active], ['live-ml-orb', status.ml_active]].forEach(([id, active]) => {
      const orb = document.getElementById(id);
      if (orb) orb.classList.toggle('active', Boolean(active));
    });

    if (historyResponse.ok && Array.isArray(history) && history.length) {
      const item = history[0];
      const spam = item.prediction === 'spam';
      const recent = document.getElementById('protection-latest');
      if (recent) {
        const preview = String(item.message || '').slice(0, 88).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
        const sender = String(item.sender || 'Unknown sender').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
        recent.innerHTML = `<article class="activity-row ${spam ? 'is-spam' : 'is-ham'}"><div class="activity-time">${new Date(item.created_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</div><div class="activity-copy"><span class="activity-sender">${sender}</span><p>${preview}</p></div><div class="activity-result"><span class="table-prediction ${spam ? 'spam' : 'ham'}">${spam ? 'SPAM' : 'SAFE'}</span><strong>${(Number(item.confidence || 0) * 100).toFixed(0)}% confidence</strong><small class="risk-label ${spam ? 'risk-high' : 'risk-low'}">${spam ? 'HIGH' : 'LOW'} RISK</small></div></article>`;
      }
    }
    const error = document.getElementById('protection-error') || document.getElementById('settings-error');
    if (error) error.textContent = '';
  } catch (error) {
    const notice = document.getElementById('protection-error') || document.getElementById('settings-error');
    if (notice) notice.textContent = error.message;
  }
}

refreshProtectionStatus();
window.setInterval(refreshProtectionStatus, 15000);
