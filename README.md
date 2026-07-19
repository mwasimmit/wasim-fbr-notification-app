# FBR E-Posting Notification Monitor

A modern, light-weight, zero-dependency Windows desktop application built in Python to monitor real-time update notices and PDF announcements from the Federal Board of Revenue (FBR) web portal.

## 🚀 Key Features

* **Real-time Background Scraping**: Scrapes the FBR website on a customizable background thread to prevent GUI freezing.
* **Modern Dark UI**: Features a sleek, responsive card-based layout customized with dark blue/slate theme aesthetics.
* **Notification Alerts**: Plays a native system bell sound and triggers a custom borderless popup alert on your desktop when new notices are posted.
* **Integrated PDF Download**: Enables downloading PDF circulars and notices directly to your local computer with a single click.
* **Customizable Refresh Interval**: Allows switching the checking interval (from 5 minutes up to 6 hours) instantly through a dropdown selector.
* **Manual Override**: A manual "Refresh Now" button is available to pull instant live updates.

---

## 🛠️ Technology Stack

* **Language**: Python 3.x
* **GUI Engine**: Tkinter (Standard library, customized styles)
* **HTML Parsing**: Custom-extended parser using standard `html.parser.HTMLParser`
* **Network Requests**: Built-in `urllib.request` with manual user-agent spoofing to avoid server blocking.

---

## 📂 Project Structure

```text
wasim-fbr-notification-app/
│
├── monitor_app.py      # Main desktop GUI application
├── test_parser.py      # Independent CLI test script for HTML parsing
├── .gitignore          # Repository git ignore configuration
└── README.md           # Documentation
```

---

## 💻 How to Run & Distribute

There are two ways to run the application:

### Option A: Standalone Executable (`.exe`) - *Recommended for sharing*
If you compile the application (or receive the compiled `FBRNotificationMonitor.exe` from `dist/` directory):
* **Zero Prerequisites**: The recipient **does not** need Python, Git, or any other software installed on their Windows PC.
* **Self-Contained**: The `.exe` contains the Python interpreter, visual libraries, and scripts packaged into a single double-clickable file.
* **Auto Startup**: The very first time the recipient double-clicks the `.exe`, it will automatically register itself with their Windows Startup.
* **How to share**: Just send the `FBRNotificationMonitor.exe` file directly to them via email, USB, or file sharing.

### Option B: Running from Source Code (Python)
If you want to run the application directly from the source code:
1. **Prerequisites**: Make sure Python 3.x is installed on your computer.
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

## 🔍 How It Works

### Client-Server Architecture
1. **Server Side (FBR Server)**: Hosts the ASP.NET notification portal at `hrms.fbr.gov.pk`. It serves the standard server-rendered page containing list details and hosts the static PDF documents.
2. **Client Side (This App)**: Fetches the raw HTML, parses the table row-by-row, filters out the last 5 posts, updates the UI cards, and handles saving files to your local drive.

### Sample Flow
```text
[FBR Web Portal] ──(Raw HTML)──> [HTML Parser] ──(Extract 5 records)──> [UI Cards Grid]
                                                                           │
                                                                   [New Update Found?]
                                                                           ├── Yes ──> Play Sound & Display Toast Alert
                                                                           └── No  ──> Wait for next scheduled run
```
