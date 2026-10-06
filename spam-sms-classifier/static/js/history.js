let currentHistoryFilter = 'all';
let currentHistory = [];

const historyEscape = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[character]);

function renderHistory() {
  const list = document.getElementById('history-list');
  const count = document.getElementById('history-count');
  if (!list) return;
  const filtered = currentHistory.filter((item) => currentHistoryFilter === 'all' || item.prediction === currentHistoryFilter);
  if (!filtered.length) {
    list.innerHTML = '<div class="activity-empty">No phone activity for this filter yet.</div>';
    if (count) count.textContent = '0 messages';
    return;
  }

  list.innerHTML = filtered.map((item) => {
    const spam = item.prediction === 'spam';
    const date = item.created_at ? new Date(item.created_at) : null;
    const timestamp = date && !Number.isNaN(date.valueOf())
      ? date.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
      : 'Time unavailable';
    const preview = String(item.message || '').slice(0, 88);
    const confidence = (Number(item.confidence || 0) * 100).toFixed(0);
    return `<article class="activity-row ${spam ? 'is-spam' : 'is-ham'}">
      <div class="activity-time">${historyEscape(timestamp)}<small>${historyEscape(item.sender || 'Unknown sender')}</small></div>
      <div class="activity-copy"><span class="activity-sender">${historyEscape(item.sender || 'Unknown sender')}</span><p>${historyEscape(preview || 'Message preview unavailable')}</p></div>
      <div class="activity-result"><span class="table-prediction ${spam ? 'spam' : 'ham'}">${spam ? 'SPAM' : 'SAFE'}</span><strong>${confidence}% confidence</strong><small class="risk-label ${spam ? 'risk-high' : 'risk-low'}">${historyEscape(item.risk_level || (spam ? 'HIGH' : 'LOW'))} RISK</small></div>
    </article>`;
  }).join('');
  if (count) count.textContent = `${filtered.length} message${filtered.length === 1 ? '' : 's'}`;
}

async function fetchHistory() {
  try {
    const response = await fetch('/api/history');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'SMS history could not be loaded.');
    currentHistory = Array.isArray(data) ? data : [];
    renderHistory();
    document.getElementById('history-error').textContent = '';
  } catch (error) {
    document.getElementById('history-error').textContent = error.message;
  }
}

document.querySelectorAll('[data-filter]').forEach((button) => {
  button.addEventListener('click', () => {
    currentHistoryFilter = button.dataset.filter || 'all';
    document.querySelectorAll('[data-filter]').forEach((item) => item.classList.toggle('active', item === button));
    renderHistory();
  });
});

fetchHistory();
window.setInterval(fetchHistory, 15000);