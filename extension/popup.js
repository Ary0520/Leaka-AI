document.addEventListener('DOMContentLoaded', () => {
  const btnRecord = document.getElementById('btn-record');
  const btnStop = document.getElementById('btn-stop');
  const statusDot = document.getElementById('status-dot');
  const statusLabel = document.getElementById('status-label');
  const btnExtractCookies = document.getElementById('btn-extract-cookies');
  const cookieStatus = document.getElementById('cookie-status');
  const envSelect = document.getElementById('env-select');
  const envWarning = document.getElementById('env-warning');
  
  // Settings
  const btnSettings = document.getElementById('btn-settings');
  const settingsPanel = document.getElementById('settings-panel');
  const mainView = document.getElementById('main-view');
  const inputBackendUrl = document.getElementById('backend-url');
  const inputApiKey = document.getElementById('api-key');
  const btnSaveSettings = document.getElementById('btn-save-settings');

  // Default config
  let config = {
    backendUrl: 'http://localhost:8000',
    selectedEnvId: null,
    apiKey: ''
  };

  // Load config
  chrome.storage.local.get(['leakaConfig', 'isRecording'], (data) => {
    if (data.leakaConfig) {
      config = { ...config, ...data.leakaConfig };
    }
    inputBackendUrl.value = config.backendUrl;
    inputApiKey.value = config.apiKey || '';
    
    // Force open settings if no API key
    if (!config.apiKey) {
      settingsPanel.style.display = 'block';
      mainView.style.display = 'none';
      return;
    }
    
    if (data.isRecording) {
      setRecordingState(true);
    }

    fetchEnvironments();
  });

  // Settings toggle
  btnSettings.addEventListener('click', () => {
    if (settingsPanel.style.display === 'block') {
      settingsPanel.style.display = 'none';
      mainView.style.display = 'block';
    } else {
      settingsPanel.style.display = 'block';
      mainView.style.display = 'none';
    }
  });

  btnSaveSettings.addEventListener('click', () => {
    config.backendUrl = inputBackendUrl.value.replace(/\/$/, "");
    config.apiKey = inputApiKey.value.trim();
    chrome.storage.local.set({ leakaConfig: config }, () => {
      settingsPanel.style.display = 'none';
      mainView.style.display = 'block';
      fetchEnvironments();
    });
  });

  envSelect.addEventListener('change', (e) => {
    config.selectedEnvId = e.target.value;
    chrome.storage.local.set({ leakaConfig: config });
  });

  async function fetchEnvironments() {
    try {
      envSelect.innerHTML = '<option value="">Loading environments...</option>';
      envSelect.disabled = true;
      btnRecord.disabled = true;
      btnExtractCookies.disabled = true;

      const res = await fetch(`${config.backendUrl}/api/vault/context`, { headers: { 'Authorization': `Bearer ${config.apiKey}` } });
      if (res.status === 401) {
        alert('Invalid API Key. Please check settings.');
        settingsPanel.style.display = 'block';
        mainView.style.display = 'none';
        return;
      }
      if (!res.ok) throw new Error('Failed to fetch contexts');
      const data = await res.json();
      
      envSelect.innerHTML = '';
      if (!data.applications || data.applications.length === 0) {
        envWarning.style.display = 'block';
        return;
      }
      
      envWarning.style.display = 'none';
      
      data.applications.forEach(app => {
        const optgroup = document.createElement('optgroup');
        optgroup.label = app.name;
        
        if (app.environments && app.environments.length > 0) {
          app.environments.forEach(env => {
            const opt = document.createElement('option');
            opt.value = env.id;
            opt.textContent = `${env.name}`;
            if (config.selectedEnvId && config.selectedEnvId == env.id) {
              opt.selected = true;
            }
            optgroup.appendChild(opt);
          });
        } else {
          const opt = document.createElement('option');
          opt.disabled = true;
          opt.textContent = `No environments setup`;
          optgroup.appendChild(opt);
        }
        
        envSelect.appendChild(optgroup);
      });
      
      envSelect.disabled = false;
      
      // Auto-select first available if none selected
      if (!config.selectedEnvId && envSelect.options.length > 0) {
        for(let i=0; i<envSelect.options.length; i++){
          if(!envSelect.options[i].disabled){
             envSelect.selectedIndex = i;
             config.selectedEnvId = envSelect.value;
             chrome.storage.local.set({ leakaConfig: config });
             break;
          }
        }
      }

      if (config.selectedEnvId) {
        btnRecord.disabled = false;
        btnExtractCookies.disabled = false;
      }

    } catch (e) {
      envSelect.innerHTML = '<option value="">Error connecting to backend</option>';
    }
  }

  btnRecord.addEventListener('click', () => {
    if (!config.selectedEnvId) return alert('Select an environment first');
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
    if (!config.selectedEnvId) return alert('Select an environment first');
    
    btnExtractCookies.textContent = 'Extracting...';
    btnExtractCookies.disabled = true;

    try {
      const response = await chrome.runtime.sendMessage({ 
        action: 'extract_cookies'
      });
      
      if (response && response.success) {
        cookieStatus.style.display = 'block';
        setTimeout(() => { cookieStatus.style.display = 'none'; }, 3000);
      } else {
        alert('Failed to push state: ' + (response?.error || 'Unknown error'));
      }
    } catch (e) {
      alert('Error: ' + e.message);
    } finally {
      btnExtractCookies.textContent = 'Push to Selected Environment';
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
      envSelect.disabled = true;
    } else {
      btnRecord.style.display = 'block';
      btnStop.style.display = 'none';
      statusDot.classList.remove('active');
      statusLabel.textContent = 'Idle';
      statusLabel.style.color = 'var(--secondary)';
      envSelect.disabled = false;
    }
  }
});
