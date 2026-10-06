let currentFilter = 'all';
let historyData = [];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[character]);
}

function getMessage(item) {
  return item.message || item.text || '';
}

async function fetchHistory() {
  try {
    const response = await fetch('/api/history');
    const data = await response.json();
    if (!response.ok || !data) throw new Error('Unable to load history');

    historyData = Array.isArray(data) ? data : (Array.isArray(data.history) ? data.history : []);
    renderHistory();
  } catch (error) {
    console.error('History error:', error);
    const tbody = document.getElementById('history-tbody');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="5">Unable to load history.</td></tr>';
    }
  }
}

function renderHistory() {
  const tbody = document.getElementById('history-tbody');
  const countEl = document.getElementById('history-count');
  if (!tbody) return;

  const filtered = historyData.filter((item) => {
    const term = document.getElementById('history-search')?.value.toLowerCase() || '';
    return (currentFilter === 'all' || item.prediction === currentFilter)
      && getMessage(item).toLowerCase().includes(term);
  });

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="5">No records match your current filter.</td></tr>';
    if (countEl) countEl.textContent = '0 records';
    return;
  }

  tbody.innerHTML = filtered.map((item) => {
    const message = getMessage(item);
    const text = message ? message.slice(0, 48) + (message.length > 48 ? '...' : '') : 'N/A';
    const isSpam = item.prediction === 'spam';
    const pred = isSpam ? 'SPAM' : 'HAM';
    const confidence = Number.isFinite(Number(item.confidence)) ? `${(Number(item.confidence) * 100).toFixed(1)}%` : '0.0%';
    const createdAt = item.created_at ? new Date(item.created_at).toLocaleString() : 'N/A';
    return `
      <tr>
        <td>${item.id}</td>
        <td>${escapeHtml(text)}</td>
        <td><span class="table-prediction ${isSpam ? 'spam' : 'ham'}">${pred}</span></td>
        <td>${confidence}</td>
        <td>${escapeHtml(createdAt)}</td>
      </tr>
    `;
  }).join('');

  if (countEl) {
    countEl.textContent = `${filtered.length} record${filtered.length !== 1 ? 's' : ''}`;
  }
}

const searchInput = document.getElementById('history-search');
if (searchInput) {
  searchInput.addEventListener('input', renderHistory);
}

document.querySelectorAll('.filter-btn').forEach((button) => {
  button.addEventListener('click', () => {
    currentFilter = button.dataset.filter || 'all';
    document.querySelectorAll('.filter-btn').forEach((btn) => btn.classList.toggle('active', btn === button));
    renderHistory();
  });
});

document.getElementById('btn-refresh-history')?.addEventListener('click', fetchHistory);

fetchHistory();
