import re

def update_background():
    path = r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\extension\background.js"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_code = """    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0] || !tabs[0].url) {
        sendResponse({ success: false, error: 'No active tab URL' });
        return;
      }
      
      const url = new URL(tabs[0].url);
      const domain = url.hostname;
      
      chrome.cookies.getAll({ domain }, async (cookies) => {
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

          const res = await fetch('http://localhost:8000/api/vault/cookies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              workspace_id: message.workspaceId,
              domain: domain,
              cookies: playwrightCookies
            })
          });
          
          if (!res.ok) throw new Error('Backend returned ' + res.status);
          sendResponse({ success: true });
        } catch (error) {
          console.error(error);
          sendResponse({ success: false, error: error.message });
        }
      });
    });"""

    new_code = """    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
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

            const res = await fetch('http://localhost:8000/api/vault/cookies', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                workspace_id: message.workspaceId,
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
    });"""

    content = content.replace(old_code, new_code)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated background.js to grab localStorage and fix cookie query")

if __name__ == "__main__":
    update_background()
