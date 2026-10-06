const homeEscapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[character]);

async function loadHomeOverview() {
  const statsStatus = document.getElementById('home-data-status');
  const historyBody = document.getElementById('home-history-body');
  const historyStatus = document.getElementById('home-history-status');

  try {
    const response = await fetch('/api/stats');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Database connection error. Statistics are unavailable.');

    document.getElementById('home-stat-total').textContent = Number(data.total_messages ?? data.total ?? 0).toLocaleString();
    document.getElementById('home-stat-spam').textContent = Number(data.spam_messages ?? data.spam ?? 0).toLocaleString();
    document.getElementById('home-stat-ham').textContent = Number(data.ham_messages ?? data.ham ?? 0).toLocaleString();
    document.getElementById('home-stat-rate').textContent = `${Number(data.spam_percentage ?? data.spam_percent ?? 0).toFixed(1)}%`;
    if (statsStatus) statsStatus.textContent = '';
  } catch (error) {
    if (statsStatus) statsStatus.textContent = error.message;
  }

  try {
    const response = await fetch('/api/history');
    const items = await response.json();
    if (!response.ok) throw new Error(items.error || 'Database connection error. Recent scans are unavailable.');
    if (!historyBody) return;
    if (!items.length) {
      historyBody.innerHTML = '<tr><td colspan="5">No scans have been recorded yet.</td></tr>';
      return;
    }
    historyBody.innerHTML = items.slice(0, 5).map((item) => {
      const isSpam = item.prediction === 'spam';
      const confidence = (Number(item.confidence || 0) * 100).toFixed(1);
      const createdAt = item.created_at ? new Date(item.created_at).toLocaleString() : '—';
      return `<tr>
        <td>${homeEscapeHtml(item.id)}</td>
        <td class="message-cell">${homeEscapeHtml(item.message)}</td>
        <td><span class="table-prediction ${isSpam ? 'spam' : 'ham'}">${isSpam ? 'SPAM' : 'HAM'}</span></td>
        <td>${confidence}%</td>
        <td>${homeEscapeHtml(createdAt)}</td>
      </tr>`;
    }).join('');
    if (historyStatus) historyStatus.textContent = '';
  } catch (error) {
    if (historyBody) historyBody.innerHTML = '<tr><td colspan="5">Unable to load recent scans.</td></tr>';
    if (historyStatus) historyStatus.textContent = error.message;
  }
}

loadHomeOverview();