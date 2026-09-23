# Leaka AI - Chrome Extension

This Chrome Extension serves as the primary Developer Experience (DevEx) bridge for Leaka AI's enterprise testing capabilities. 

## Features
1. **Natural Language Prompt Generation:** Automatically records clicks, inputs, and navigations while you interact with your app. It translates these actions into high-level Natural Language Prompts for the Leaka AI agent.
2. **Vault Cookie Extraction:** Instantly bypass complex SSO and MFA workflows by extracting active session cookies directly from your browser and pushing them securely to the Leaka Vault for Azure backend injection.

## Installation
1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer Mode** in the top right.
3. Click **Load unpacked** and select this `extension/` directory.

## Usage
- Click the Leaka AI extension icon in your toolbar.
- Click **Start Recording Prompts** to begin capturing your flow.
- Click **Stop & Save to Vault** to push the generated prompts to the backend.
- Use **Push Cookies to Leaka Vault** to push your active session cookies to the backend.
