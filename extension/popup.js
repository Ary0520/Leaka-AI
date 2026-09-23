document.addEventListener('DOMContentLoaded', () => {
  const btnRecord = document.getElementById('btn-record');
  const btnStop = document.getElementById('btn-stop');
  const statusDot = document.getElementById('status-dot');
  const statusLabel = document.getElementById('status-label');
  const btnExtractCookies = document.getElementById('btn-extract-cookies');
  const cookieStatus = document.getElementById('cookie-status');
  const workspaceInput = document.getElementById('workspace-id');

  // Load current recording state
  chrome.storage.local.get(['isRecording', 'workspaceId'], (data) => {
    if (data.isRecording) {
      setRecordingState(true);
    }
    if (data.workspaceId) {
      workspaceInput.value = data.workspaceId;
    }
  });

  workspaceInput.addEventListener('change', (e) => {
    chrome.storage.local.set({ workspaceId: e.target.value });
  });

  btnRecord.addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'start_recording' }, () => {
      setRecordingState(true);
    });
  });

  btnStop.addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'stop_recording' }, () => {
      setRecordingState(false);
    });
  });

  btnExtractCookies.addEventListener('click', async () => {
    btnExtractCookies.textContent = 'Extracting...';
    btnExtractCookies.disabled = true;

    try {
      const response = await chrome.runtime.sendMessage({ 
        action: 'extract_cookies',
        workspaceId: workspaceInput.value || 'personal'
      });
      
      if (response && response.success) {
        cookieStatus.style.display = 'block';
        setTimeout(() => { cookieStatus.style.display = 'none'; }, 3000);
      } else {
        alert('Failed to push cookies: ' + (response?.error || 'Unknown error'));
      }
    } catch (e) {
      alert('Error: ' + e.message);
    } finally {
      btnExtractCookies.textContent = 'Push Cookies to Leaka Vault';
      btnExtractCookies.disabled = false;
    }
  });

  function setRecordingState(isRecording) {
    if (isRecording) {
      btnRecord.style.display = 'none';
      btnStop.style.display = 'block';
      statusDot.classList.add('active');
      statusLabel.textContent = 'Recording natural language prompts...';
      statusLabel.style.color = 'var(--success)';
    } else {
      btnRecord.style.display = 'block';
      btnStop.style.display = 'none';
      statusDot.classList.remove('active');
      statusLabel.textContent = 'Idle';
      statusLabel.style.color = 'var(--secondary)';
    }
  }
});
