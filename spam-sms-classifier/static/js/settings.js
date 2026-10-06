/**
 * settings.js — SpamGuard Settings & Account Controls
 */

function showAlert(message, type = 'success') {
  const alertBox = document.getElementById('settings-alert');
  if (!alertBox) return;

  alertBox.className = `alert-box alert-${type}`;
  alertBox.textContent = message;
  alertBox.style.display = 'block';

  setTimeout(() => {
    alertBox.style.display = 'none';
  }, 4000);
}

async function loadSettings() {
  try {
    const [settingsRes, statusRes, userRes] = await Promise.all([
      fetch('/api/settings').then(r => r.ok ? r.json() : null),
      fetch('/api/protection-status').then(r => r.ok ? r.json() : null),
      fetch('/api/auth/me').then(r => r.ok ? r.json() : null)
    ]);

    // 1. Toggles
    if (settingsRes) {
      const elSms = document.getElementById('setting-sms-monitoring');
      const elAi = document.getElementById('setting-ai-detection');
      const elAlerts = document.getElementById('setting-high-risk-alerts');
      const elMask = document.getElementById('setting-mask-numbers');
      const elHide = document.getElementById('setting-hide-content');

      if (elSms) elSms.checked = Boolean(settingsRes.sms_monitoring);
      if (elAi) elAi.checked = Boolean(settingsRes.ai_detection);
      if (elAlerts) elAlerts.checked = Boolean(settingsRes.high_risk_alerts);
      if (elMask) elMask.checked = Boolean(settingsRes.mask_phone_numbers);
      if (elHide) elHide.checked = Boolean(settingsRes.hide_sms_content);
    }

    // 2. Device Status
    if (statusRes) {
      const isConnected = Boolean(statusRes.phone_connected);
      const phoneStatus = document.getElementById('settings-phone-status');
      const phoneBadge = document.getElementById('settings-phone-badge');

      if (phoneStatus) {
        if (isConnected) {
          phoneStatus.textContent = 'SpamGuard Companion App · Last active ' + (statusRes.last_seen ? new Date(statusRes.last_seen).toLocaleTimeString() : 'just now');
        } else {
          phoneStatus.textContent = 'No Android device communicating with backend.';
        }
      }

      if (phoneBadge) {
        if (isConnected) {
          phoneBadge.className = 'badge badge-connected';
          phoneBadge.innerHTML = '<span class="pulse-dot"></span> CONNECTED';
        } else {
          phoneBadge.className = 'badge badge-inactive';
          phoneBadge.textContent = 'NOT CONNECTED';
        }
      }
    }

    // 3. User Info
    if (userRes) {
      const nameInput = document.getElementById('account-name');
      const emailInput = document.getElementById('account-email');
      if (nameInput && userRes.name) nameInput.value = userRes.name;
      if (emailInput && userRes.email) emailInput.value = userRes.email;
    }

  } catch (err) {
    console.error('Error loading settings:', err);
  }
}

async function savePreferences() {
  const btn = document.getElementById('btn-save-settings');
  if (btn) btn.disabled = true;

  const payload = {
    sms_monitoring: document.getElementById('setting-sms-monitoring')?.checked ? 1 : 0,
    ai_detection: document.getElementById('setting-ai-detection')?.checked ? 1 : 0,
    high_risk_alerts: document.getElementById('setting-high-risk-alerts')?.checked ? 1 : 0,
    mask_phone_numbers: document.getElementById('setting-mask-numbers')?.checked ? 1 : 0,
    hide_sms_content: document.getElementById('setting-hide-content')?.checked ? 1 : 0,
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      showAlert('Security preferences saved successfully.', 'success');
    } else {
      showAlert(data.error || 'Failed to save preferences.', 'error');
    }
  } catch (err) {
    showAlert('Server unreachable. Could not save preferences.', 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function updateName() {
  const nameInput = document.getElementById('account-name');
  const name = nameInput?.value.trim();
  if (!name || name.length < 2) {
    showAlert('Name must be at least 2 characters.', 'error');
    return;
  }

  try {
    const res = await fetch('/api/account/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'profile', name })
    });
    const data = await res.json();
    if (res.ok) {
      showAlert('Display name updated successfully.', 'success');
    } else {
      showAlert(data.error || 'Failed to update name.', 'error');
    }
  } catch (err) {
    showAlert('Unable to update name.', 'error');
  }
}

async function updatePassword() {
  const curPw = document.getElementById('current-password')?.value;
  const newPw = document.getElementById('new-password')?.value;
  const cnfPw = document.getElementById('confirm-password')?.value;

  if (!curPw || !newPw) {
    showAlert('Please enter both current and new password.', 'error');
    return;
  }
  if (newPw.length < 6) {
    showAlert('New password must be at least 6 characters.', 'error');
    return;
  }
  if (newPw !== cnfPw) {
    showAlert('New passwords do not match.', 'error');
    return;
  }

  try {
    const res = await fetch('/api/account/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'password',
        current_password: curPw,
        new_password: newPw,
        confirm_password: cnfPw
      })
    });
    const data = await res.json();
    if (res.ok) {
      showAlert('Password updated successfully.', 'success');
      document.getElementById('current-password').value = '';
      document.getElementById('new-password').value = '';
      document.getElementById('confirm-password').value = '';
    } else {
      showAlert(data.error || 'Failed to update password.', 'error');
    }
  } catch (err) {
    showAlert('Unable to update password.', 'error');
  }
}

async function handleLogout() {
  if (!confirm('Are you sure you want to sign out of SpamGuard?')) return;
  try {
    const res = await fetch('/api/auth/logout', { method: 'POST' });
    const data = await res.json();
    window.location.href = data.redirect || '/login';
  } catch (err) {
    window.location.href = '/login';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadSettings();

  document.getElementById('btn-save-settings')?.addEventListener('click', savePreferences);
  document.getElementById('btn-update-name')?.addEventListener('click', updateName);
  document.getElementById('btn-update-password')?.addEventListener('click', updatePassword);
  document.getElementById('btn-logout')?.addEventListener('click', handleLogout);
});
