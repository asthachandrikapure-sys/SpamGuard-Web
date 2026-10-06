/**
 * inbox.js — SpamGuard AI SMS Security Inbox
 * Features:
 *   - Gmail-like security inbox with left sidebar folders
 *   - Folders: All SMS, Spam SMS, Safe SMS, Important, Trash, High Risk
 *   - Real-time MySQL actions: Star/Important, Read/Unread, Move to Trash, Restore
 *   - Live search by sender or message content
 *   - Risk-level filtering chips
 *   - Detail inspection view with full AI diagnostics
 *   - Automatic live polling every 8 seconds
 */

let allMessages = [];
let currentFolder = 'all';
let currentRiskFilter = 'all';
let searchQuery = '';
let activeDetailId = null;

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

function formatTime(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '—';
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch (e) {
    return '—';
  }
}

function formatFullDateTime(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString([], {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  } catch (e) {
    return '—';
  }
}

async function loadInboxData() {
  try {
    const [statsRes, historyRes] = await Promise.all([
      fetch('/api/stats').then(r => r.ok ? r.json() : null),
      fetch('/api/history?limit=500').then(r => r.ok ? r.json() : [])
    ]);

    // 1. Update Sidebar Counts & Detection Rate
    if (statsRes) {
      const total = Number(statsRes.total_messages ?? statsRes.total ?? 0);
      const spam = Number(statsRes.spam_messages ?? statsRes.spam ?? 0);
      const safe = Number(statsRes.ham_messages ?? statsRes.ham ?? 0);
      const high = Number(statsRes.high_risk_messages ?? 0);
      const important = Number(statsRes.important_messages ?? 0);
      const trashed = Number(statsRes.trashed_messages ?? 0);
      const rate = total ? ((spam / total) * 100).toFixed(1) : '0.0';

      const elAll = document.getElementById('count-all');
      const elSpam = document.getElementById('count-spam');
      const elSafe = document.getElementById('count-safe');
      const elHigh = document.getElementById('count-high');
      const elImportant = document.getElementById('count-important');
      const elTrash = document.getElementById('count-trash');
      const elRate = document.getElementById('sidebar-rate');

      if (elAll) elAll.textContent = total;
      if (elSpam) elSpam.textContent = spam;
      if (elSafe) elSafe.textContent = safe;
      if (elHigh) elHigh.textContent = high;
      if (elImportant) elImportant.textContent = important;
      if (elTrash) elTrash.textContent = trashed;
      if (elRate) elRate.textContent = `${rate}%`;

      // Update spam summary bar values
      const elSpTotal = document.getElementById('sp-total');
      const elSpHigh = document.getElementById('sp-high');
      const elSpMed = document.getElementById('sp-medium');
      const elSpLow = document.getElementById('sp-low');

      if (elSpTotal) elSpTotal.textContent = spam;
      if (elSpHigh) elSpHigh.textContent = high;
      if (elSpMed) elSpMed.textContent = '0';
      if (elSpLow) elSpLow.textContent = Math.max(0, spam - high);
    }

    // 2. Update Messages List
    allMessages = Array.isArray(historyRes) ? historyRes : [];
    renderInboxList();

  } catch (err) {
    console.error('Failed to load inbox data:', err);
    const errEl = document.getElementById('inbox-error');
    if (errEl) errEl.textContent = 'Unable to reach SpamGuard server. Retrying...';
  }
}

function getFilteredMessages() {
  return allMessages.filter(item => {
    const isTrashed = Boolean(item.is_trashed);

    // If viewing trash, show only trashed messages
    if (currentFolder === 'trash') {
      if (!isTrashed) return false;
    } else {
      // In all other folders, hide trashed messages
      if (isTrashed) return false;

      if (currentFolder === 'spam' && item.prediction !== 'spam') return false;
      if (currentFolder === 'safe' && item.prediction !== 'ham') return false;
      if (currentFolder === 'important' && !item.is_important) return false;
      if (currentFolder === 'high_risk' && item.risk_level !== 'HIGH') return false;
    }

    // 2. Risk chip filter
    if (currentRiskFilter === 'HIGH' && item.risk_level !== 'HIGH') return false;
    if (currentRiskFilter === 'LOW' && item.risk_level !== 'LOW') return false;

    // 3. Search filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const msg = String(item.message || '').toLowerCase();
      const snd = String(item.sender || '').toLowerCase();
      if (!msg.includes(q) && !snd.includes(q)) return false;
    }

    return true;
  });
}

function renderInboxList() {
  if (activeDetailId !== null) return;

  const listContainer = document.getElementById('sms-list');
  const countLabel = document.getElementById('inbox-count');
  if (!listContainer) return;

  const filtered = getFilteredMessages();

  if (countLabel) {
    countLabel.textContent = `Showing ${filtered.length} of ${allMessages.length}`;
  }

  if (filtered.length === 0) {
    let emptyIcon = '📥';
    let emptyMsg = 'No messages in this folder';
    let emptySub = 'When your Android phone receives SMS messages, they will appear here automatically.';

    if (currentFolder === 'spam') {
      emptyIcon = '🛡️';
      emptyMsg = 'No spam detected';
      emptySub = 'Great news! SpamGuard has not flagged any unwanted or suspicious messages.';
    } else if (currentFolder === 'safe') {
      emptyIcon = '📨';
      emptyMsg = 'No safe messages yet';
      emptySub = 'Legitimate incoming messages will be cataloged here.';
    } else if (currentFolder === 'important') {
      emptyIcon = '⭐';
      emptyMsg = 'No starred messages';
      emptySub = 'Click the star icon on any SMS to pin it to your Important folder.';
    } else if (currentFolder === 'trash') {
      emptyIcon = '🗑️';
      emptyMsg = 'Trash is empty';
      emptySub = 'Deleted SMS messages are moved here.';
    } else if (currentFolder === 'high_risk') {
      emptyIcon = '🎉';
      emptyMsg = 'Zero high risk threats';
      emptySub = 'No dangerous phishing, scam, or high-risk SMS detected.';
    }

    listContainer.innerHTML = `
      <div class="sms-empty">
        <div style="font-size:2.2rem;margin-bottom:10px">${emptyIcon}</div>
        <strong style="font-size:1.05rem;color:var(--text);margin-bottom:6px;display:block">${emptyMsg}</strong>
        <p style="font-size:0.875rem;color:var(--text-muted);max-width:380px;margin:0 auto">${emptySub}</p>
      </div>
    `;
    return;
  }

  listContainer.innerHTML = filtered.map(item => {
    const isSpam = item.prediction === 'spam';
    const isHighRisk = item.risk_level === 'HIGH';
    const isUnread = !item.is_read;
    const isStarred = Boolean(item.is_important);
    const isTrashed = Boolean(item.is_trashed);
    const sender = escapeHtml(item.sender || 'Unknown');
    const preview = escapeHtml(item.message || '');
    const time = formatTime(item.created_at);
    const conf = (Number(item.confidence || 0) * 100).toFixed(0);

    return `
      <div class="sms-row ${isUnread ? 'unread' : ''}" onclick="openMessageDetail(${item.id})">
        <button class="sms-star-btn ${isStarred ? 'starred' : ''}" onclick="event.stopPropagation(); toggleImportant(${item.id})" title="${isStarred ? 'Unstar' : 'Mark Important'}">
          ${isStarred ? '★' : '☆'}
        </button>
        <div class="sms-indicator ${isSpam ? 'spam' : 'safe'}" title="${isSpam ? 'Spam Detected' : 'Safe Message'}"></div>
        <div class="sms-sender" title="${sender}">${sender}</div>
        <div class="sms-snippet" title="${preview}">${preview}</div>
        <div class="sms-tags">
          <span class="badge ${isSpam ? 'badge-spam' : 'badge-safe'}">${isSpam ? 'SPAM' : 'SAFE'}</span>
          <span class="badge ${isHighRisk ? 'badge-high' : 'badge-low'}">${item.risk_level || (isSpam ? 'HIGH' : 'LOW')}</span>
          <span style="font-size:0.75rem;color:var(--text-muted);font-weight:600">${conf}%</span>
        </div>
        <div class="sms-time">${time}</div>
        <button class="sms-action-icon" onclick="event.stopPropagation(); toggleTrash(${item.id}, ${isTrashed ? 0 : 1})" title="${isTrashed ? 'Restore' : 'Move to Trash'}">
          ${isTrashed ? '↩️' : '🗑️'}
        </button>
      </div>
    `;
  }).join('');
}

async function toggleImportant(smsId) {
  const item = allMessages.find(m => m.id === smsId);
  if (!item) return;

  const newVal = item.is_important ? 0 : 1;
  item.is_important = newVal;
  renderInboxList();
  updateDetailButtons(item);

  try {
    await fetch(`/api/sms/${smsId}/important`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_important: newVal })
    });
    loadInboxData();
  } catch (err) {
    console.error('Failed to update important status:', err);
  }
}

async function toggleReadStatus(smsId, isRead) {
  const item = allMessages.find(m => m.id === smsId);
  if (!item) return;

  item.is_read = isRead ? 1 : 0;
  renderInboxList();
  updateDetailButtons(item);

  try {
    const endpoint = isRead ? `/api/sms/${smsId}/read` : `/api/sms/${smsId}/unread`;
    await fetch(endpoint, { method: 'POST' });
    loadInboxData();
  } catch (err) {
    console.error('Failed to update read status:', err);
  }
}

async function toggleTrash(smsId, trashedState = 1) {
  const item = allMessages.find(m => m.id === smsId);
  if (!item) return;

  item.is_trashed = trashedState;
  if (activeDetailId === smsId) {
    closeMessageDetail();
  } else {
    renderInboxList();
  }

  try {
    await fetch(`/api/sms/${smsId}/trash`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_trashed: trashedState })
    });
    loadInboxData();
  } catch (err) {
    console.error('Failed to move to trash:', err);
  }
}

function updateDetailButtons(item) {
  const starBtn = document.getElementById('detail-star-btn');
  const unreadBtn = document.getElementById('detail-unread-btn');
  const trashBtn = document.getElementById('detail-trash-btn');

  if (starBtn) {
    const isStarred = Boolean(item.is_important);
    starBtn.innerHTML = isStarred ? '★ Starred' : '☆ Star';
    starBtn.classList.toggle('active', isStarred);
    starBtn.onclick = () => toggleImportant(item.id);
  }

  if (unreadBtn) {
    unreadBtn.innerHTML = item.is_read ? '✉️ Mark Unread' : '📬 Mark Read';
    unreadBtn.onclick = () => toggleReadStatus(item.id, !item.is_read);
  }

  if (trashBtn) {
    const isTrashed = Boolean(item.is_trashed);
    trashBtn.innerHTML = isTrashed ? '↩️ Restore' : '🗑️ Delete';
    trashBtn.onclick = () => toggleTrash(item.id, isTrashed ? 0 : 1);
  }
}

function openMessageDetail(smsId) {
  const item = allMessages.find(m => m.id === smsId);
  if (!item) return;

  activeDetailId = smsId;

  // Hide list and search toolbar, show detail panel
  const listContainer = document.getElementById('sms-list');
  const toolbar = document.querySelector('.inbox-toolbar');
  const summaryBar = document.getElementById('spam-summary-bar');
  const detailPanel = document.getElementById('msg-detail-panel');

  if (listContainer) listContainer.style.display = 'none';
  if (toolbar) toolbar.style.display = 'none';
  if (summaryBar) summaryBar.style.display = 'none';
  if (detailPanel) detailPanel.style.display = 'block';

  // Mark as read visually & call API
  item.is_read = 1;
  fetch(`/api/sms/${smsId}/read`, { method: 'POST' }).catch(() => {});

  updateDetailButtons(item);

  const isSpam = item.prediction === 'spam';
  const isHighRisk = item.risk_level === 'HIGH';
  const conf = (Number(item.confidence || 0) * 100).toFixed(1);

  const elAvatar = document.getElementById('msg-detail-avatar');
  const elSender = document.getElementById('msg-detail-sender');
  const elTime = document.getElementById('msg-detail-time');
  const elContent = document.getElementById('msg-detail-content');
  const elClass = document.getElementById('msg-stat-class');
  const elConf = document.getElementById('msg-stat-conf');
  const elRisk = document.getElementById('msg-stat-risk');
  const elBadges = document.getElementById('msg-detail-badges');

  if (elAvatar) {
    elAvatar.textContent = isSpam ? '🚨' : '🛡️';
    elAvatar.style.background = isSpam ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)';
  }

  if (elSender) elSender.textContent = item.sender || 'Unknown Sender';
  if (elTime) elTime.textContent = formatFullDateTime(item.created_at);
  if (elContent) elContent.textContent = item.message || '';

  if (elClass) {
    elClass.innerHTML = `<span class="badge ${isSpam ? 'badge-spam' : 'badge-safe'}">${isSpam ? 'SPAM' : 'SAFE'}</span>`;
  }

  if (elConf) elConf.textContent = `${conf}%`;

  if (elRisk) {
    elRisk.innerHTML = `<span class="badge ${isHighRisk ? 'badge-high' : 'badge-low'}">${item.risk_level || (isSpam ? 'HIGH' : 'LOW')} RISK</span>`;
  }

  if (elBadges) {
    elBadges.innerHTML = `
      <span class="badge ${isSpam ? 'badge-spam' : 'badge-safe'}">${isSpam ? 'SPAM' : 'SAFE'}</span>
      <span class="badge ${isHighRisk ? 'badge-high' : 'badge-low'}">${item.risk_level} RISK</span>
      ${item.is_important ? '<span class="badge" style="background:rgba(234,179,8,0.2);color:#eab308">⭐ IMPORTANT</span>' : ''}
    `;
  }
}

function closeMessageDetail() {
  activeDetailId = null;

  const listContainer = document.getElementById('sms-list');
  const toolbar = document.querySelector('.inbox-toolbar');
  const summaryBar = document.getElementById('spam-summary-bar');
  const detailPanel = document.getElementById('msg-detail-panel');

  if (detailPanel) detailPanel.style.display = 'none';
  if (listContainer) listContainer.style.display = 'block';
  if (toolbar) toolbar.style.display = 'flex';

  if (currentFolder === 'spam' && summaryBar) {
    summaryBar.style.display = 'block';
  }

  renderInboxList();
}

// ─────────────────────────────────────────────
// EVENT LISTENERS & SETUP
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Sidebar Folder Navigation
  const sidebarItems = document.querySelectorAll('.inbox-sidebar .sidebar-item');
  sidebarItems.forEach(item => {
    item.addEventListener('click', () => {
      sidebarItems.forEach(s => s.classList.remove('active'));
      item.classList.add('active');

      currentFolder = item.dataset.filter || 'all';

      // Update header titles
      const titleEl = document.getElementById('inbox-panel-title');
      const subEl = document.getElementById('inbox-panel-sub');
      const summaryBar = document.getElementById('spam-summary-bar');

      if (currentFolder === 'all') {
        if (titleEl) titleEl.innerHTML = '📥 All SMS';
        if (subEl) subEl.textContent = 'All messages analyzed by SpamGuard AI.';
        if (summaryBar) summaryBar.style.display = 'none';
      } else if (currentFolder === 'spam') {
        if (titleEl) titleEl.innerHTML = '🚨 Spam SMS';
        if (subEl) subEl.textContent = 'Messages detected as potentially unwanted, fraudulent, or harmful.';
        if (summaryBar) summaryBar.style.display = 'block';
      } else if (currentFolder === 'safe') {
        if (titleEl) titleEl.innerHTML = '🛡️ Safe SMS';
        if (subEl) subEl.textContent = 'Clean and legitimate messages verified by SpamGuard AI.';
        if (summaryBar) summaryBar.style.display = 'none';
      } else if (currentFolder === 'important') {
        if (titleEl) titleEl.innerHTML = '⭐ Important SMS';
        if (subEl) subEl.textContent = 'Messages you have starred or flagged as important.';
        if (summaryBar) summaryBar.style.display = 'none';
      } else if (currentFolder === 'trash') {
        if (titleEl) titleEl.innerHTML = '🗑️ Trash';
        if (subEl) subEl.textContent = 'Deleted SMS messages. Click restore icon to recover.';
        if (summaryBar) summaryBar.style.display = 'none';
      } else if (currentFolder === 'high_risk') {
        if (titleEl) titleEl.innerHTML = '⚠️ High Risk SMS';
        if (subEl) subEl.textContent = 'High confidence malicious SMS requiring immediate caution.';
        if (summaryBar) summaryBar.style.display = 'none';
      }

      closeMessageDetail();
    });
  });

  // Risk Filter Chips
  const filterChips = document.querySelectorAll('.inbox-filters .filter-chip');
  filterChips.forEach(chip => {
    chip.addEventListener('click', () => {
      filterChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentRiskFilter = chip.dataset.risk || 'all';
      renderInboxList();
    });
  });

  // Search Input
  const searchInput = document.getElementById('sms-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.trim();
      renderInboxList();
    });
  }

  // Back to Inbox Button
  const backBtn = document.getElementById('back-to-inbox');
  if (backBtn) {
    backBtn.addEventListener('click', closeMessageDetail);
  }

  // Initial Load
  loadInboxData();
  // Auto-polling every 8 seconds for live automatic protection
  setInterval(loadInboxData, 8000);
});
