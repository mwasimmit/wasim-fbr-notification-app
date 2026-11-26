# FBR Transfer Posting Notifications Monitor

A modern, lightweight Windows desktop application built in Python to monitor real-time FBR Admin Notifications and PDF announcements from the Federal Board of Revenue (FBR) web portal.

## 🚀 Key Features

* **Real-time Background Scraping**: Scrapes the FBR website on a customizable background thread to prevent GUI freezing.
* **Modern Dark UI**: Features a sleek, responsive card-based layout with dark blue/slate theme aesthetics.
* **Notification Alerts**: Plays a native system bell sound and triggers a custom borderless popup alert on your desktop when new notices are posted.
* **Smart Popup Buttons**: Popup shows a **"Dismiss"** button (closes the popup only) and an **"Open App"** button (brings the main window to the foreground).
* **Single Instance**: Launching the app when it is already running brings the existing window to focus instead of opening a second copy.
* **Integrated PDF Download**: Download PDF circulars and notices directly to your local computer with a single click.
* **Customizable Refresh Interval**: Switch the checking interval (from 5 minutes up to 6 hours) instantly through a dropdown selector.
* **Manual Override**: A manual "Refresh Now" button is available to pull instant live updates.
* **System Tray with Badge Count**: Minimises to the system tray and shows a red badge with the unread notification count.
* **Desktop & Start Menu Shortcuts**: Created automatically on first launch for easy access.
* **Windows Startup**: Optional toggle to run automatically when Windows starts.
* **Signed Executable**: The `.exe` is signed with a code-signing certificate, removing the "Unknown Publisher" UAC warning on install.

---

## 🛠️ Technology Stack

* **Language**: Python 3.x
* **GUI Engine**: Tkinter (Standard library, customized styles)
* **HTML Parsing**: Custom-extended parser using standard `html.parser.HTMLParser`
* **Network Requests**: Built-in `urllib.request` with manual user-agent spoofing to avoid server blocking.
* **System Tray**: `pystray` + `Pillow` for tray icon and badge rendering.
* **Code Signing**: PowerShell `Set-AuthenticodeSignature` with self-signed certificate.

---

## 📂 Project Structure

```text
wasim-fbr-notification-app/
│
├── monitor_app.py              # Main desktop GUI application
├── test_parser.py              # Independent CLI test script for HTML parsing
├── FBRNotificationMonitor.spec # PyInstaller build configuration
├── sign_exe.ps1                # PowerShell script to sign the .exe (removes Unknown Publisher warning)
├── .gitignore                  # Repository git ignore configuration
└── README.md                   # Documentation
```

---

## 💻 How to Run & Distribute

### Option A: Standalone Executable (`.exe`) — *Recommended for sharing*

If you receive the compiled `FBRNotificationMonitor.exe` from the `dist/` directory or from the [GitHub Releases](https://github.com/mwasimmit/wasim-fbr-notification-app/releases) page:

* **Zero Prerequisites**: The recipient **does not** need Python, Git, or any other software installed.
* **Self-Contained**: The `.exe` bundles the Python interpreter, GUI libraries, and scripts into one double-clickable file.
* **Signed**: The `.exe` is signed, so Windows will show the publisher name instead of "Unknown Publisher" in the UAC prompt.
* **Auto Shortcuts**: On first launch, Desktop and Start Menu shortcuts are created automatically.

> **Note on SmartScreen**: Because the certificate is self-signed (not from a paid public CA), Windows SmartScreen may still show a "Windows protected your PC" warning on the very first run. Click **"More info" → "Run anyway"** to proceed. This warning disappears after a few successful runs build SmartScreen reputation.

### Option B: Running from Source Code (Python)

1. **Prerequisites**: Python 3.x and the required packages:
   ```bash
   pip install pillow pystray
   ```
2. Clone the repository:
   ```bash
   git clone https://github.com/mwasimmit/wasim-fbr-notification-app.git
   cd wasim-fbr-notification-app
   ```
3. Run the application:
   ```bash
   python monitor_app.py
   ```

---

## 🔐 Signing the Executable (Developers)

To re-sign the `.exe` after rebuilding it:
```powershell
# Run this in PowerShell (run as Administrator for the first time)
.\sign_exe.ps1
```
This will:
1. Create a self-signed code-signing certificate (valid 5 years) if one doesn't exist.
2. Add it to the local Trusted Root store (requires Admin on first run).
3. Sign `dist\FBRNotificationMonitor.exe` with a DigiCert timestamp.

---

## 🔍 How It Works

### Client-Server Architecture
1. **Server Side (FBR Server)**: Hosts the ASP.NET notification portal at `hrms.fbr.gov.pk`, serving the page containing posting details and static PDF documents.
2. **Client Side (This App)**: Fetches the raw HTML, parses the notification table row-by-row, displays the last 10 posts as cards, and handles PDF downloads and new-posting alerts.

### Sample Flow
```text
[FBR Web Portal] ──(Raw HTML)──> [HTML Parser] ──(Extract 10 records)──> [UI Cards Grid]
                                                                           │
                                                                   [New Update Found?]
                                                                           ├── Yes ──> Play Sound & Display Toast Alert
                                                                           │           [Dismiss] closes popup only
                                                                           │           [Open App] restores main window
                                                                           └── No  ──> Wait for next scheduled run
```
