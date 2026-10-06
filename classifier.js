const smsInput = document.getElementById('sms-input');
const charCounter = document.getElementById('char-counter');
const btnClassify = document.getElementById('btn-classify');
const btnClear = document.getElementById('btn-clear');
const resultPlaceholder = document.getElementById('result-placeholder');
const resultContent = document.getElementById('result-content');
const resultError = document.getElementById('result-error');
const errorMessage = document.getElementById('error-message');
const spinner = document.getElementById('spinner');
const resultBadge = document.getElementById('result-badge');
const resultLabel = document.getElementById('result-label');
const resultVerdict = document.getElementById('result-verdict');
const detailConfidence = document.getElementById('detail-confidence');
const detailModel = document.getElementById('detail-model');
const detailPrediction = document.getElementById('detail-prediction');
const detailRisk = document.getElementById('detail-risk');
const detailTime = document.getElementById('detail-time');
const resultGuidance = document.getElementById('result-guidance');
const confidencePct = document.getElementById('confidence-pct');
const confidenceBar = document.getElementById('confidence-bar');
const analyzedMsgText = document.getElementById('analyzed-msg-text');

if (smsInput && charCounter) {
  const updateCounter = () => {
    charCounter.textContent = `${smsInput.value.length} / 1000`;
  };

  smsInput.addEventListener('input', updateCounter);
  updateCounter();
}

function showResultState(type) {
  resultPlaceholder.classList.add('hidden');
  resultContent.classList.add('hidden');
  resultError.classList.add('hidden');

  if (type === 'content') {
    resultContent.classList.remove('hidden');
  } else if (type === 'error') {
    resultError.classList.remove('hidden');
  } else {
    resultPlaceholder.classList.remove('hidden');
  }
}

async function classifyMessage() {
  if (!smsInput) return;

  const message = smsInput.value.trim();
  if (!message) {
    showResultState('error');
    errorMessage.textContent = 'Please enter an SMS message.';
    return;
  }

  if (btnClassify) btnClassify.disabled = true;
  if (spinner) spinner.classList.remove('hidden');

  try {
    const response = await fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message, text: message })
    });

    const data = await response.json();
    if (!response.ok || !data || data.error) {
      throw new Error(data?.error || 'Prediction failed.');
    }

    const isSpam = data.prediction === 'spam';
    const normalized = isSpam ? 'SPAM' : 'HAM / NOT SPAM';
    const confidence = Number(data.confidence) * 100;

    if (resultBadge) {
      resultBadge.classList.toggle('spam', isSpam);
    }

    if (resultLabel) {
      resultLabel.textContent = isSpam ? 'SPAM DETECTED' : 'HAM / NOT SPAM';
    }

    if (resultVerdict) {
      resultVerdict.textContent = isSpam ? '⚠ SPAM DETECTED' : '✓ SAFE MESSAGE';
    }

    if (detailConfidence) {
      detailConfidence.textContent = `${confidence.toFixed(1)}%`;
    }

    if (detailModel) {
      detailModel.textContent = data.model || 'Trained SMS Model';
    }

    if (detailPrediction) detailPrediction.textContent = normalized;
    if (detailRisk) detailRisk.textContent = data.risk_level || (isSpam ? 'HIGH' : 'LOW');
    if (detailTime) detailTime.textContent = data.created_at ? new Date(data.created_at).toLocaleString() : 'Just now';
    if (resultGuidance) {
      resultGuidance.textContent = isSpam
        ? 'Do not open links or share personal information with this sender.'
        : 'This message was classified as ham. Stay cautious with unexpected links.';
    }

    if (confidencePct) {
      confidencePct.textContent = `${Math.max(0, Math.min(100, confidence)).toFixed(0)}%`;
    }

    if (confidenceBar) {
      confidenceBar.style.width = `${Math.max(0, Math.min(100, confidence))}%`;
    }

    if (analyzedMsgText) {
      analyzedMsgText.textContent = message;
    }

    showResultState('content');
  } catch (err) {
    showResultState('error');
    errorMessage.textContent = err.message || 'Unable to classify the message right now.';
  } finally {
    if (btnClassify) btnClassify.disabled = false;
    if (spinner) spinner.classList.add('hidden');
  }
}

if (btnClassify) {
  btnClassify.addEventListener('click', classifyMessage);
}

if (btnClear) {
  btnClear.addEventListener('click', () => {
    if (smsInput) smsInput.value = '';
    if (charCounter) charCounter.textContent = '0 / 1000';
    showResultState('placeholder');
  });
}

document.querySelectorAll('.sample-btn').forEach((button) => {
  button.addEventListener('click', () => {
    if (!smsInput) return;
    smsInput.value = button.dataset.msg || '';
    if (charCounter) charCounter.textContent = `${smsInput.value.length} / 1000`;
    classifyMessage();
  });
});
