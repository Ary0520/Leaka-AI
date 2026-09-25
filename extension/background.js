let isRecording = false;
let recordedEvents = [];

// Initialize state
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ 
    isRecording: false, 
    events: [],
    leakaConfig: { backendUrl: 'http://localhost:8000', selectedEnvId: null }
  });
});

// Listen for messages from popup or content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'start_recording') {
    isRecording = true;
    recordedEvents = [];
    chrome.storage.local.set({ isRecording: true, events: [] });
    // Inject content script into active tab to ensure it's ready
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.scripting.executeScript({
          target: { tabId: tabs[0].id },
          files: ['content_script.js']
        }).catch(err => console.log('Script already injected or error:', err));
      }
    });
    sendResponse({ success: true });
    
  } else if (message.action === 'stop_recording') {
    isRecording = false;
    chrome.storage.local.set({ isRecording: false });
    
    // Process recorded events into Natural Language Prompts
    chrome.storage.local.get(['events', 'leakaConfig'], (data) => {
      const config = data.leakaConfig || { backendUrl: 'http://localhost:8000', selectedEnvId: null };
      const nlpPrompts = processEventsToPrompts(data.events || []);
      // Push to backend
      pushPromptsToVault(nlpPrompts, config)
        .then(() => {
          chrome.storage.local.set({ events: [] });
        })
        .catch(console.error);
    });
    sendResponse({ success: true });
    
  } else if (message.action === 'capture_event') {
    if (isRecording) {
      chrome.storage.local.get(['events'], (data) => {
        const events = data.events || [];
        events.push(message.event);
        chrome.storage.local.set({ events });
      });
    }
    sendResponse({ success: true });
    
  } else if (message.action === 'extract_cookies') {
    chrome.storage.local.get(['leakaConfig'], (data) => {
      const config = data.leakaConfig || { backendUrl: 'http://localhost:8000', selectedEnvId: null };
      
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs[0] || !tabs[0].url) {
          sendResponse({ success: false, error: 'No active tab URL' });
          return;
        }
        
        const tabUrl = tabs[0].url;
        const urlObj = new URL(tabUrl);
        const domain = urlObj.hostname;
        const origin = urlObj.origin;
        
        // We will grab cookies for the URL, AND inject a script to grab localStorage
        chrome.scripting.executeScript({
          target: { tabId: tabs[0].id },
          func: () => {
            const ls = [];
            for (let i = 0; i < localStorage.length; i++) {
              const key = localStorage.key(i);
              ls.push({ name: key, value: localStorage.getItem(key) });
            }
            return ls;
          }
        }, (injectionResults) => {
          const lsData = (injectionResults && injectionResults[0] && injectionResults[0].result) ? injectionResults[0].result : [];
          
          chrome.cookies.getAll({ url: tabUrl }, async (cookies) => {
            try {
              // Format cookies for Playwright storageState
              const playwrightCookies = cookies.map(c => ({
                name: c.name,
                value: c.value,
                domain: c.domain,
                path: c.path,
                expires: c.expirationDate || -1,
                httpOnly: c.httpOnly,
                secure: c.secure,
                sameSite: c.sameSite === 'no_restriction' ? 'None' : (c.sameSite === 'unspecified' ? 'Lax' : c.sameSite)
              }));

              const res = await fetch(`${config.backendUrl}/api/vault/cookies`, {
                method: 'POST',
                headers: { 
                  'Content-Type': 'application/json',
                  'Authorization': `Bearer ${config.apiKey}`
                },
                body: JSON.stringify({
                  environment_id: config.selectedEnvId ? parseInt(config.selectedEnvId) : null,
                  domain: domain,
                  cookies: playwrightCookies,
                  origins: [
                    {
                      origin: origin,
                      localStorage: lsData
                    }
                  ]
                })
              });
              
              if (!res.ok) throw new Error('Backend returned ' + res.status);
              sendResponse({ success: true });
            } catch (error) {
              console.error(error);
              sendResponse({ success: false, error: error.message });
            }
          });
        });
      });
    });
    return true; // Keep message channel open for async
  }
});

function processEventsToPrompts(events) {
  const prompts = [];
  
  for (const ev of events) {
    if (ev.type === 'click') {
      const identifier = ev.text || ev.cssSelector || 'element';
      prompts.push(`Click on "${identifier}"`);
    } else if (ev.type === 'input' || ev.type === 'change') {
      const identifier = ev.text || ev.cssSelector || 'input';
      prompts.push(`Type "${ev.value}" into "${identifier}"`);
    } else if (ev.type === 'navigate') {
      prompts.push(`Navigate to ${ev.url}`);
    }
  }
  
  return prompts;
}

async function pushPromptsToVault(prompts, config) {
  if (!prompts.length) return;
  
  await fetch(`${config.backendUrl}/api/vault/prompts`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${config.apiKey}`
    },
    body: JSON.stringify({
      environment_id: config.selectedEnvId ? parseInt(config.selectedEnvId) : null,
      prompts: prompts
    })
  });
}
