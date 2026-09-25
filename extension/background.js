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
      pushPromptsToVault(nlpPrompts, config, message.testName)
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

function formatIdentifier(ev) {
  // For form elements, text is highly volatile (it changes as you type).
  // We should prioritize structural attributes over text.
  
  if (ev.selector_strategy === 'placeholder') {
    const match = ev.selector.match(/placeholder="(.*?)"/);
    if (match) return `the "${match[1]}" input`;
  }
  
  if (ev.selector_strategy === 'aria-label') {
    const match = ev.selector.match(/aria-label="(.*?)"/);
    if (match) return `the "${match[1]}" element`;
  }
  
  if (ev.selector_strategy === 'testid') {
    const match = ev.selector.match(/"(.*?)"/);
    if (match) return `the "${match[1].replace(/[-_]/g, ' ')}"`;
  }

  if (ev.selector_strategy === 'name') {
    const match = ev.selector.match(/name="(.*?)"/);
    if (match) return `the "${match[1].replace(/[-_]/g, ' ')}" field`;
  }
  
  if (ev.text && ev.text.trim().length > 0) {
    let cleanText = ev.text.trim().replace(/\n/g, " ");
    if (cleanText.length > 40) cleanText = cleanText.substring(0, 40) + "...";
    return `"${cleanText}"`;
  }
  
  if (ev.selector_strategy === 'id') {
    const match = ev.selector.match(/#(.*)/);
    if (match) return `the "${match[1].replace(/[-_]/g, ' ')}"`;
  }
  
  if (ev.selector_strategy === 'alt') {
    const match = ev.selector.match(/alt="(.*?)"/);
    if (match) return `the "${match[1]}" image`;
  }
  
  return `the ${ev.tag_name || 'element'}`;
}

function processEventsToPrompts(events) {
  const prompts = [];
  
  for (const ev of events) {
    const target = formatIdentifier(ev);
    
    if (ev.type === 'click') {
      prompts.push({ type: 'click', target, text: `Click on ${target}` });
      
    } else if (ev.type === 'input' || ev.type === 'change') {
      if (ev.value === undefined || ev.value === "") continue; // Ignore clearing empty fields on submit
      
      const cleanValue = ev.value.replace(/\n/g, "");
      if (cleanValue === "") continue;
      
      prompts.push({ type: 'type', target, value: cleanValue, text: `Type "${cleanValue}" into ${target}` });
      
    } else if (ev.type === 'keydown' && ev.key === 'Enter') {
      prompts.push({ type: 'enter', target, text: `Press Enter` });
      
    } else if (ev.type === 'navigate') {
      prompts.push({ type: 'navigate', target: 'browser', text: `Navigate to ${ev.url}` });
    }
  }
  
  // Deduplicate consecutive typing events targeting the exact same element
  const compressed = [];
  for (const p of prompts) {
    if (compressed.length > 0 && p.type === 'type' && compressed[compressed.length-1].type === 'type') {
       if (compressed[compressed.length-1].target === p.target) {
         // The user is just continuing to type in the same field. Override with the accumulated full string.
         compressed[compressed.length-1] = p;
         continue;
       }
    }
    compressed.push(p);
  }
  
  // Return just the string instructions
  return compressed.map(p => p.text);
}

async function pushPromptsToVault(prompts, config, testName) {
  if (!prompts.length) return;
  
  await fetch(`${config.backendUrl}/api/vault/prompts`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${config.apiKey}`
    },
    body: JSON.stringify({
      environment_id: config.selectedEnvId ? parseInt(config.selectedEnvId) : null,
      prompts: prompts,
      name: testName || null
    })
  });
}
