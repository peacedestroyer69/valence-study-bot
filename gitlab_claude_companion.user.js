// ==UserScript==
// @name         GitLab Claude Companion
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  A premium sidebar companion for GitLab Merge Requests. Copy MR context/diff for Claude Web UI or chat directly with Claude using your Anthropic API Key.
// @author       Antigravity
// @match        *://gitlab.com/*
// @match        *://*.gitlab.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setClipboard
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      api.anthropic.com
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    // Helper: check if we are on a Merge Request page
    function isMergeRequestPage() {
        return window.location.pathname.includes('/merge_requests/');
    }

    if (!isMergeRequestPage()) {
        // Listen for SPA navigation in GitLab (GitLab uses page:change or pushState)
        document.addEventListener('page:change', function() {
            if (isMergeRequestPage()) {
                initCompanion();
            }
        });
        return;
    }

    initCompanion();

    function initCompanion() {
        // Prevent duplicate injection
        if (document.getElementById('claude-companion-container')) return;

        // --- STYLES ---
        const style = document.createElement('style');
        style.innerHTML = `
            #claude-companion-toggle {
                position: fixed;
                bottom: 24px;
                right: 24px;
                width: 56px;
                height: 56px;
                border-radius: 50%;
                background: linear-gradient(135deg, #d97706, #b45309);
                box-shadow: 0 8px 32px rgba(180, 83, 9, 0.4);
                cursor: pointer;
                z-index: 999999;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #ffffff;
                font-size: 24px;
                transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.3s;
                border: 2px solid rgba(255, 255, 255, 0.2);
            }
            #claude-companion-toggle:hover {
                transform: scale(1.1) rotate(10deg);
                box-shadow: 0 12px 40px rgba(180, 83, 9, 0.6);
            }
            #claude-companion-toggle:active {
                transform: scale(0.95);
            }
            #claude-companion-sidebar {
                position: fixed;
                top: 0;
                right: -450px;
                width: 420px;
                height: 100vh;
                background: rgba(17, 24, 39, 0.95);
                backdrop-filter: blur(16px);
                -webkit-backdrop-filter: blur(16px);
                border-left: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: -10px 0 40px rgba(0, 0, 0, 0.5);
                z-index: 999998;
                transition: right 0.4s cubic-bezier(0.16, 1, 0.3, 1);
                display: flex;
                flex-direction: column;
                color: #f3f4f6;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }
            #claude-companion-sidebar.open {
                right: 0;
            }
            .cc-header {
                padding: 20px;
                background: linear-gradient(90deg, rgba(217, 119, 6, 0.15), rgba(17, 24, 39, 0));
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .cc-header h3 {
                margin: 0;
                font-size: 18px;
                font-weight: 700;
                letter-spacing: 0.5px;
                background: linear-gradient(90deg, #fbbf24, #f59e0b);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .cc-close {
                background: none;
                border: none;
                color: #9ca3af;
                font-size: 20px;
                cursor: pointer;
                transition: color 0.2s;
            }
            .cc-close:hover {
                color: #f3f4f6;
            }
            .cc-content {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            .cc-section {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                padding: 16px;
            }
            .cc-section-title {
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #9ca3af;
                margin-top: 0;
                margin-bottom: 12px;
                font-weight: 600;
            }
            .cc-btn {
                width: 100%;
                padding: 10px 14px;
                border-radius: 8px;
                border: none;
                background: rgba(217, 119, 6, 0.1);
                color: #fbbf24;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                border: 1px solid rgba(217, 119, 6, 0.2);
                margin-bottom: 8px;
            }
            .cc-btn:hover:not(:disabled) {
                background: #d97706;
                color: #ffffff;
                box-shadow: 0 4px 12px rgba(217, 119, 6, 0.3);
            }
            .cc-btn:active:not(:disabled) {
                transform: translateY(1px);
            }
            .cc-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .cc-btn-primary {
                background: linear-gradient(135deg, #d97706, #b45309);
                color: #ffffff;
                border: none;
            }
            .cc-btn-primary:hover:not(:disabled) {
                background: linear-gradient(135deg, #ea580c, #c2410c);
            }
            .cc-input {
                width: 100%;
                padding: 8px 12px;
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
                margin-bottom: 8px;
                box-sizing: border-box;
            }
            .cc-input:focus {
                outline: none;
                border-color: #fbbf24;
            }
            .cc-chat-area {
                flex: 1;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                background: rgba(0, 0, 0, 0.2);
                display: flex;
                flex-direction: column;
                height: 300px;
                overflow: hidden;
            }
            .cc-messages {
                flex: 1;
                overflow-y: auto;
                padding: 12px;
                display: flex;
                flex-direction: column;
                gap: 8px;
                font-size: 13px;
            }
            .cc-message {
                max-width: 85%;
                padding: 8px 12px;
                border-radius: 8px;
                line-height: 1.4;
                word-wrap: break-word;
                white-space: pre-wrap;
            }
            .cc-message.user {
                background: #1e3a8a;
                color: #eff6ff;
                align-self: flex-end;
                border-bottom-right-radius: 2px;
            }
            .cc-message.claude {
                background: rgba(255, 255, 255, 0.08);
                color: #f3f4f6;
                align-self: flex-start;
                border-bottom-left-radius: 2px;
            }
            .cc-message.system {
                background: rgba(239, 68, 68, 0.1);
                color: #fca5a5;
                align-self: center;
                font-style: italic;
                font-size: 11px;
                max-width: 95%;
            }
            .cc-chat-input-container {
                display: flex;
                padding: 8px;
                background: rgba(0, 0, 0, 0.4);
                border-top: 1px solid rgba(255, 255, 255, 0.08);
                gap: 6px;
            }
            .cc-chat-input {
                flex: 1;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                color: #ffffff;
                padding: 8px 12px;
                font-size: 13px;
                resize: none;
                height: 36px;
                box-sizing: border-box;
                font-family: inherit;
            }
            .cc-chat-input:focus {
                outline: none;
                border-color: #fbbf24;
            }
            .cc-send-btn {
                background: #d97706;
                border: none;
                color: white;
                border-radius: 6px;
                width: 36px;
                height: 36px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.2s;
            }
            .cc-send-btn:hover {
                background: #fbbf24;
            }
            .cc-send-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .cc-toast {
                position: fixed;
                bottom: 90px;
                right: 24px;
                background: rgba(16, 185, 129, 0.95);
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
                z-index: 1000000;
                opacity: 0;
                transform: translateY(10px);
                transition: opacity 0.3s, transform 0.3s;
                pointer-events: none;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            .cc-toast.show {
                opacity: 1;
                transform: translateY(0);
            }
            .cc-loader {
                width: 16px;
                height: 16px;
                border: 2px solid rgba(255,255,255,0.3);
                border-radius: 50%;
                border-top-color: white;
                animation: spin 0.8s linear infinite;
                display: inline-block;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .cc-small-copy {
                padding: 2px 6px;
                font-size: 11px;
                background: rgba(217, 119, 6, 0.15);
                border: 1px solid rgba(217, 119, 6, 0.3);
                color: #fbbf24;
                border-radius: 4px;
                cursor: pointer;
                margin-left: 8px;
                display: inline-flex;
                align-items: center;
                gap: 4px;
                transition: all 0.2s;
            }
            .cc-small-copy:hover {
                background: #d97706;
                color: white;
            }
        `;
        document.head.appendChild(style);

        // --- DOM STRUCTURE ---
        const container = document.createElement('div');
        container.id = 'claude-companion-container';

        // Toggle Button
        const toggle = document.createElement('div');
        toggle.id = 'claude-companion-toggle';
        toggle.innerHTML = '🤖';
        toggle.title = 'Open Claude Companion';
        container.appendChild(toggle);

        // Sidebar
        const sidebar = document.createElement('div');
        sidebar.id = 'claude-companion-sidebar';
        sidebar.innerHTML = `
            <div class="cc-header">
                <h3><span>🤖</span> GitLab Claude Companion</h3>
                <button class="cc-close" id="cc-close-btn">&times;</button>
            </div>
            <div class="cc-content">
                <!-- CLIPBOARD COPIER SECTION -->
                <div class="cc-section">
                    <h4 class="cc-section-title">Clipboard Exporter (For claude.ai)</h4>
                    <button class="cc-btn cc-btn-primary" id="cc-btn-copy-prompt">
                        📋 Copy Full MR Prompt
                    </button>
                    <button class="cc-btn" id="cc-btn-copy-diff">
                        📄 Copy Raw MR Diff
                    </button>
                    <button class="cc-btn" id="cc-btn-copy-desc">
                        ✍️ Copy MR Description
                    </button>
                </div>

                <!-- DIRECT CLAUDE API INTEGRATION -->
                <div class="cc-section" style="display: flex; flex-direction: column; flex: 1;">
                    <h4 class="cc-section-title">Direct Claude API Chat</h4>
                    <input type="password" class="cc-input" id="cc-api-key" placeholder="Enter Anthropic API Key..." value="${GM_getValue('anthropic_api_key', '')}">
                    <select class="cc-input" id="cc-api-model">
                        <option value="claude-3-5-sonnet-latest">Claude 3.5 Sonnet (Recommended)</option>
                        <option value="claude-3-opus-latest">Claude 3 Opus</option>
                        <option value="claude-3-5-haiku-latest">Claude 3.5 Haiku</option>
                    </select>
                    
                    <div class="cc-chat-area">
                        <div class="cc-messages" id="cc-chat-messages">
                            <div class="cc-message claude">Hello! Please enter your API key above to start chat. I can reference the Merge Request details and diff automatically.</div>
                        </div>
                        <div class="cc-chat-input-container">
                            <textarea class="cc-chat-input" id="cc-chat-input-text" placeholder="Ask Claude..."></textarea>
                            <button class="cc-send-btn" id="cc-chat-send-btn">✈️</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        container.appendChild(sidebar);

        // Toast Notification
        const toast = document.createElement('div');
        toast.className = 'cc-toast';
        toast.id = 'cc-toast-msg';
        toast.innerHTML = '✅ Copied to clipboard!';
        container.appendChild(toast);

        document.body.appendChild(container);

        // --- BUTTON REGISTER & CLICK HANDLERS ---
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });

        document.getElementById('cc-close-btn').addEventListener('click', () => {
            sidebar.classList.remove('open');
        });

        // Save settings on edit
        const apiKeyInput = document.getElementById('cc-api-key');
        apiKeyInput.addEventListener('input', (e) => {
            GM_setValue('anthropic_api_key', e.target.value.trim());
        });

        const apiModelSelect = document.getElementById('cc-api-model');
        const savedModel = GM_getValue('anthropic_model', 'claude-3-5-sonnet-latest');
        apiModelSelect.value = savedModel;
        apiModelSelect.addEventListener('change', (e) => {
            GM_setValue('anthropic_model', e.target.value);
        });

        // 1. Copy Full Prompt
        document.getElementById('cc-btn-copy-prompt').addEventListener('click', async () => {
            const btn = document.getElementById('cc-btn-copy-prompt');
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<span class="cc-loader"></span> Fetching diff...`;

            try {
                const prompt = await buildFullPrompt();
                GM_setClipboard(prompt);
                showToast("✅ Full MR Prompt copied!");
            } catch (err) {
                console.error(err);
                showToast("❌ Failed to fetch MR diff: " + err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        });

        // 2. Copy Raw Diff
        document.getElementById('cc-btn-copy-diff').addEventListener('click', async () => {
            const btn = document.getElementById('cc-btn-copy-diff');
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<span class="cc-loader"></span> Fetching diff...`;

            try {
                const diff = await fetchDiff();
                GM_setClipboard(diff);
                showToast("✅ Raw Diff copied!");
            } catch (err) {
                console.error(err);
                showToast("❌ Failed to fetch diff: " + err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        });

        // 3. Copy Description
        document.getElementById('cc-btn-copy-desc').addEventListener('click', () => {
            const desc = getMRDescription();
            GM_setClipboard(desc);
            showToast("✅ Description copied!");
        });

        // --- INLINE BUTTONS IN DIFF VIEW ---
        injectInlineButtons();

        // Re-inject inline buttons when DOM changes (e.g. switching tabs in GitLab)
        const observer = new MutationObserver(() => {
            injectInlineButtons();
        });
        observer.observe(document.body, { childList: true, subtree: true });

        // --- DIRECT CHAT IMPLEMENTATION ---
        const chatInput = document.getElementById('cc-chat-input-text');
        const chatSendBtn = document.getElementById('cc-chat-send-btn');
        const chatMessages = document.getElementById('cc-chat-messages');

        let chatContextLoaded = false;
        let chatHistory = [];

        chatSendBtn.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        async function sendMessage() {
            const text = chatInput.value.trim();
            if (!text) return;

            const apiKey = GM_getValue('anthropic_api_key', '');
            if (!apiKey) {
                alert("Please enter your Anthropic API Key first!");
                return;
            }

            // Append user message
            appendMessage('user', text);
            chatInput.value = '';
            chatSendBtn.disabled = true;

            // Prepare history
            chatHistory.push({ role: 'user', content: text });

            // If this is the first message, load full MR context as a system prompt / context builder
            let contextText = "";
            if (!chatContextLoaded) {
                appendMessage('system', "Fetching MR context for Claude...");
                try {
                    contextText = await buildFullPrompt();
                    chatContextLoaded = true;
                } catch (e) {
                    appendMessage('system', "Warning: Could not fetch MR diff context. Sending message without diff.");
                }
            }

            // Call Anthropic API
            const model = GM_getValue('anthropic_model', 'claude-3-5-sonnet-latest');
            const messagesPayload = [...chatHistory];

            // If we have context, inject it into the first message or system prompt
            let systemPrompt = "You are Claude, a helpful code reviewer. The user is asking about a GitLab Merge Request.";
            if (contextText) {
                systemPrompt += "\n\nHere is the Merge Request context (Title, Description, and Diff):\n" + contextText;
            }

            appendMessage('claude', 'Thinking...');
            const thinkingMsgIndex = chatMessages.children.length - 1;

            GM_xmlhttpRequest({
                method: 'POST',
                url: 'https://api.anthropic.com/v1/messages',
                headers: {
                    'Content-Type': 'application/json',
                    'x-api-key': apiKey,
                    'anthropic-version': '2023-06-01',
                    'anthropic-danger-out-of-band-requests': 'true'
                },
                data: JSON.stringify({
                    model: model,
                    max_tokens: 4000,
                    system: systemPrompt,
                    messages: messagesPayload
                }),
                onload: function(res) {
                    // Remove "Thinking..." message
                    chatMessages.removeChild(chatMessages.children[thinkingMsgIndex]);
                    chatSendBtn.disabled = false;

                    try {
                        const data = JSON.parse(res.responseText);
                        if (data.error) {
                            appendMessage('system', "Error: " + data.error.message);
                            chatHistory.pop(); // Remove last user msg since it failed
                            return;
                        }

                        const reply = data.content[0].text;
                        appendMessage('claude', reply);
                        chatHistory.push({ role: 'assistant', content: reply });
                    } catch (e) {
                        appendMessage('system', "Error parsing response from Anthropic API. See console.");
                        console.error(res.responseText);
                        chatHistory.pop();
                    }
                },
                onerror: function(err) {
                    chatMessages.removeChild(chatMessages.children[thinkingMsgIndex]);
                    chatSendBtn.disabled = false;
                    appendMessage('system', "Network error connecting to Anthropic API.");
                    console.error(err);
                    chatHistory.pop();
                }
            });
        }

        function appendMessage(role, text) {
            const div = document.createElement('div');
            div.className = `cc-message ${role}`;
            div.textContent = text;
            chatMessages.appendChild(div);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    // --- HELPER METADATA EXTRACTORS ---
    function getMRTitle() {
        const titleEl = document.querySelector('h1.title') || document.querySelector('.detail-page-header .title') || document.querySelector('.mr-title');
        return titleEl ? titleEl.textContent.trim() : document.title;
    }

    function getMRDescription() {
        const descEl = document.querySelector('.description .md') || document.querySelector('.js-task-list-container');
        return descEl ? descEl.textContent.trim() : "No description provided.";
    }

    function getMRBranches() {
        const sourceEl = document.querySelector('.js-source-branch') || document.querySelector('.source-branch');
        const targetEl = document.querySelector('.js-target-branch') || document.querySelector('.target-branch');
        return {
            source: sourceEl ? sourceEl.textContent.trim() : 'unknown',
            target: targetEl ? targetEl.textContent.trim() : 'unknown'
        };
    }

    async function fetchDiff() {
        // Fetch raw diff using the MR URL + .diff extension
        const rawUrl = window.location.href.split('?')[0].split('#')[0];
        const diffUrl = rawUrl + '.diff';

        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url: diffUrl,
                onload: function(res) {
                    if (res.status >= 200 && res.status < 300) {
                        resolve(res.responseText);
                    } else {
                        reject(new Error(`HTTP ${res.status}: ${res.statusText}`));
                    }
                },
                onerror: function(err) {
                    reject(err);
                }
            });
        });
    }

    async function buildFullPrompt() {
        const title = getMRTitle();
        const desc = getMRDescription();
        const branches = getMRBranches();
        const diff = await fetchDiff();

        return `You are an expert software engineer and code reviewer.
Here is the context for my GitLab Merge Request. Please review the changes, explain what they accomplish, check for any bugs, security vulnerabilities, or performance issues, and suggest concrete improvements or code edits where appropriate.

======================================================================
MERGE REQUEST METADATA
======================================================================
Title: ${title}
URL: ${window.location.href}
Branches: ${branches.source} ➔ ${branches.target}

======================================================================
DESCRIPTION
======================================================================
${desc}

======================================================================
CHANGES (DIFF)
======================================================================
${diff}
`;
    }

    function showToast(msg) {
        const toast = document.getElementById('cc-toast-msg');
        toast.textContent = msg;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    // --- INLINE INJECTION FOR FILE DIFFS ---
    function injectInlineButtons() {
        // In GitLab MR Changes tab, each file is enclosed in a div with class .file-holder
        const fileHolders = document.querySelectorAll('.file-holder:not(.cc-button-injected)');
        if (!fileHolders.length) return;

        fileHolders.forEach(holder => {
            holder.classList.add('cc-button-injected');

            // Find file header controls where we can inject our copy button
            const fileActions = holder.querySelector('.file-actions') || holder.querySelector('.file-header-content');
            if (!fileActions) return;

            const copyBtn = document.createElement('button');
            copyBtn.className = 'cc-small-copy';
            copyBtn.innerHTML = '📋 Copy Diff';
            copyBtn.title = 'Copy this file\'s diff for Claude';

            copyBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();

                // Extract diff lines for this file specifically
                const diffLines = holder.querySelector('.diff-content') || holder.querySelector('.code-diff');
                if (diffLines) {
                    const filePathEl = holder.querySelector('.file-title-name') || holder.querySelector('.diff-file-name');
                    const filePath = filePathEl ? filePathEl.textContent.trim() : 'Unknown File';
                    const diffText = diffLines.textContent;
                    
                    const fullText = `=== Diff for File: ${filePath} ===\n${diffText}`;
                    GM_setClipboard(fullText);
                    showToast(`✅ Copied diff for ${filePath.split('/').pop()}`);
                } else {
                    showToast("❌ Could not find diff content for this file.");
                }
            });

            // Prepend or append the button
            fileActions.insertBefore(copyBtn, fileActions.firstChild);
        });
    }
})();
