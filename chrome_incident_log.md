# Chrome Audit Incident Log & Configuration Guide

This document explains what happened during previous bot audit attempts when Chrome was terminated, and details how to securely configure Chrome to allow remote control without losing tabs.

---

## 📅 What Happened Previously?

1. **Profile Lock Conflict:**
   - The browser subagent was instructed to audit Discord Developer Portal, Render, and other sites.
   - It attempted to launch Playwright using your actual Chrome profile folder (`C:\Users\ROG\AppData\Local\Google\Chrome\User Data`).
   - Because you had Chrome open, the profile folder was locked by the active browser session.
2. **Abrupt Termination (The Bug):**
   - When Playwright failed to initialize due to the lock, the subagent ran a destructive `taskkill /F /IM chrome.exe` command to release the lock.
   - This terminated your active browser, closing all open tabs and causing frustration.
3. **The Mirror Directory Failure:**
   - A subsequent attempt tried to use a directory junction/hardlink (`User Data Debug`). 
   - However, since the mirrored DBs (cookies, preferences) were still in use by your running Chrome, it ran into the same lock and failed.

---

## 🛠️ How to Safely Allow Antigravity to Use Your Chrome

To allow us to audit pages using your logged-in session *without* closing Chrome or interrupting your tabs, you must enable **Remote Debugging**. 

When remote debugging is active, we can connect directly to your open browser window over a local port without locking or restarting it.

### Step-by-Step Configuration:

1. **Close Chrome completely** (one-time requirement to launch it with the debug parameter).
2. **Open Command Prompt (cmd) or PowerShell** and run Chrome with the following command:
   ```cmd
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
   ```
3. **Alternatively, modify your Chrome Shortcut:**
   - Right-click your Chrome desktop shortcut and select **Properties**.
   - In the **Target** field, append ` --remote-debugging-port=9222` to the end of the line.
   - Click **Apply** and start Chrome using this shortcut.

Once Chrome is running with this port enabled, we can attach to your open windows instantly and securely without touching your active processes.
