import sys
import os
import ssl
import time
import threading
import urllib.request
import urllib.parse
import webbrowser
from datetime import datetime
from html.parser import HTMLParser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Custom HTML Parser for FBR Notifications page
class FBRNotificationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_tr = False
        self.in_td = False
        self.in_a = False
        self.current_href = None
        self.cells = []
        self.current_cell_data = []
        self.notifications = []
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'table' and attrs_dict.get('id') == 'gvNotification':
            self.in_table = True
        elif self.in_table and tag == 'tr':
            self.in_tr = True
            self.cells = []
        elif self.in_tr and tag == 'td':
            self.in_td = True
            self.current_cell_data = []
        elif self.in_td and tag == 'a':
            self.in_a = True
            self.current_href = attrs_dict.get('href')
            
    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
        elif tag == 'tr' and self.in_tr:
            self.in_tr = False
            if len(self.cells) >= 5:
                # Exclude the header row
                if "Notification" not in self.cells[0] and "No" not in self.cells[0]:
                    notif = {
                        "no": self.cells[0].strip(),
                        "type": self.cells[1].strip(),
                        "subject": self.cells[2].strip(),
                        "date": self.cells[3].strip(),
                        "link": self.cells[4] if len(self.cells) > 4 else None
                    }
                    self.notifications.append(notif)
        elif tag == 'td' and self.in_td:
            self.in_td = False
            if self.current_href:
                base_url = "https://hrms.fbr.gov.pk/eposting/Proposal/SearchNotification.aspx?view=ExternalLink"
                full_url = urllib.parse.urljoin(base_url, self.current_href)
                self.cells.append(full_url)
                self.current_href = None
            else:
                self.cells.append(" ".join([d for d in self.current_cell_data if d]))
        elif tag == 'a':
            self.in_a = False
            
    def handle_data(self, data):
        if self.in_td:
            self.current_cell_data.append(data.strip())

class FBRMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FBR Notification Monitor")
        self.root.geometry("850x620")
        self.root.minsize(750, 500)
        self.root.configure(bg="#0f172a") # Sleek dark background
        
        # Application state
        self.notifications = []
        self.last_checked = None
        self.update_interval_minutes = 60 # Default 1 hour
        self.is_checking = False
        self.timer_thread = None
        self.stop_timer_event = threading.Event()
        self.next_update_time = 0
        self.latest_seen_no = None
        
        # Configure styles
        self.setup_styles()
        
        # Build UI layout
        self.build_ui()
        # Add to Windows Startup automatically
        self.add_to_startup()
        
        # Initial check
        self.trigger_check()
        
        # Start background timer
        self.start_timer_thread()
        
        # Handle close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # General configurations
        style.configure("TFrame", background="#0f172a")
        style.configure("Card.TFrame", background="#1e293b", borderwidth=1, relief="solid")
        
        # Labels
        style.configure("Title.TLabel", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background="#0f172a", foreground="#94a3b8", font=("Segoe UI", 10))
        style.configure("Status.TLabel", background="#0f172a", foreground="#38bdf8", font=("Segoe UI", 9, "italic"))
        style.configure("Timer.TLabel", background="#0f172a", foreground="#a7f3d0", font=("Segoe UI", 10, "bold"))
        
        # Card Labels
        style.configure("CardNo.TLabel", background="#1e293b", foreground="#38bdf8", font=("Segoe UI", 11, "bold"))
        style.configure("CardType.TLabel", background="#1e293b", foreground="#f43f5e", font=("Segoe UI", 9, "bold"))
        style.configure("CardDate.TLabel", background="#1e293b", foreground="#64748b", font=("Segoe UI", 9))
        style.configure("CardSubject.TLabel", background="#1e293b", foreground="#e2e8f0", font=("Segoe UI", 10))
        
        # Buttons
        style.configure("Primary.TButton", background="#2563eb", foreground="#ffffff", borderwidth=0, font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Primary.TButton", background=[("active", "#1d4ed8"), ("pressed", "#1e40af")])
        
        style.configure("Secondary.TButton", background="#334155", foreground="#ffffff", borderwidth=0, font=("Segoe UI", 9), padding=5)
        style.map("Secondary.TButton", background=[("active", "#475569"), ("pressed", ("#1e293b"))])
        
        # OptionMenu/Combobox
        style.configure("TCombobox", fieldbackground="#1e293b", background="#334155", foreground="#f8fafc", font=("Segoe UI", 10))

    def build_ui(self):
        # --- Top Header Panel ---
        header_frame = ttk.Frame(self.root, padding=20)
        header_frame.pack(fill="x", side="top")
        
        # App Info
        title_label = ttk.Label(header_frame, text="FBR E-Posting Notification Monitor", style="Title.TLabel")
        title_label.pack(anchor="w")
        
        subtitle_label = ttk.Label(header_frame, text="Monitors real-time notification postings and PDF announcements", style="Subtitle.TLabel")
        subtitle_label.pack(anchor="w", pady=(2, 10))
        
        # Control Panel
        control_frame = ttk.Frame(header_frame)
        control_frame.pack(fill="x", pady=5)
        
        # Refresh Interval Picker
        interval_label = ttk.Label(control_frame, text="Refresh Interval: ", style="Subtitle.TLabel")
        interval_label.pack(side="left", padx=(0, 5))
        
        self.interval_var = tk.StringVar(value="1 Hour")
        intervals = ["5 Minutes", "15 Minutes", "30 Minutes", "1 Hour", "2 Hours", "6 Hours"]
        self.interval_menu = ttk.Combobox(control_frame, textvariable=self.interval_var, values=intervals, width=12, state="readonly")
        self.interval_menu.pack(side="left", padx=5)
        self.interval_menu.bind("<<ComboboxSelected>>", self.on_interval_changed)
        
        # Manual Refresh Button
        self.refresh_btn = ttk.Button(control_frame, text="🔄 Refresh Now", style="Primary.TButton", command=self.trigger_check)
        self.refresh_btn.pack(side="left", padx=15)
        
        # Timer / Status Text
        self.timer_label = ttk.Label(control_frame, text="Next update in: Calculating...", style="Timer.TLabel")
        self.timer_label.pack(side="right", padx=10)
        
        # --- Divider Line ---
        divider = tk.Frame(self.root, height=1, bg="#334155")
        divider.pack(fill="x", padx=20, pady=5)
        
        # --- Main Notification List Panel ---
        self.list_frame = ttk.Frame(self.root, padding=20)
        self.list_frame.pack(fill="both", expand=True)
        
        # Placeholder or loading label
        self.loading_label = ttk.Label(self.list_frame, text="Loading updates...", style="Title.TLabel", foreground="#94a3b8")
        self.loading_label.pack(expand=True)
        
        # --- Bottom Status bar ---
        status_bar = ttk.Frame(self.root, padding=(10, 5))
        status_bar.pack(fill="x", side="bottom")
        
        self.status_label = ttk.Label(status_bar, text="Status: Ready", style="Status.TLabel")
        self.status_label.pack(side="left")
        
        # Link to source page
        source_label = ttk.Label(status_bar, text="Source Page (HRMS FBR)", foreground="#38bdf8", cursor="hand2", font=("Segoe UI", 9, "underline"))
        source_label.pack(side="right")
        source_label.bind("<Button-1>", lambda e: webbrowser.open("https://hrms.fbr.gov.pk/eposting/Proposal/SearchNotification.aspx?view=ExternalLink"))

    def on_interval_changed(self, event=None):
        val = self.interval_var.get()
        if "Minute" in val:
            mins = int(val.split()[0])
        elif "Hour" in val:
            mins = int(val.split()[0]) * 60
        else:
            mins = 60
            
        self.update_interval_minutes = mins
        self.status_label.config(text=f"Status: Interval updated to {val}")
        
        # Recalculate next run time immediately
        self.next_update_time = time.time() + (self.update_interval_minutes * 60)

    def trigger_check(self):
        if self.is_checking:
            return
        
        self.is_checking = True
        self.status_label.config(text="Status: Fetching updates...")
        self.refresh_btn.state(["disabled"])
        
        # Run parsing in background thread to avoid freezing GUI
        threading.Thread(target=self.fetch_notifications_worker, daemon=True).start()

    def fetch_notifications_worker(self):
        url = "https://hrms.fbr.gov.pk/eposting/Proposal/SearchNotification.aspx?view=ExternalLink"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx) as response:
                html = response.read().decode('utf-8', errors='ignore')
                
            parser = FBRNotificationParser()
            parser.feed(html)
            
            # Fetch top 5
            top_5 = parser.notifications[:5]
            
            # Check if there is any new update
            is_new_update = False
            if top_5 and self.latest_seen_no:
                # Compare the topmost notification number
                if top_5[0]['no'] != self.latest_seen_no:
                    is_new_update = True
            
            if top_5:
                self.latest_seen_no = top_5[0]['no']
                
            self.root.after(0, self.update_ui_with_results, top_5, is_new_update, None)
            
        except Exception as e:
            self.root.after(0, self.update_ui_with_results, [], False, str(e))

    def update_ui_with_results(self, notifications, is_new_update, error):
        self.is_checking = False
        self.refresh_btn.state(["!disabled"])
        self.last_checked = datetime.now()
        
        # Reset next update timer
        self.next_update_time = time.time() + (self.update_interval_minutes * 60)
        
        if error:
            self.status_label.config(text=f"Status: Error checking updates ({self.last_checked.strftime('%H:%M:%S')})")
            messagebox.showerror("Connection Error", f"Failed to retrieve notifications from FBR website:\n{error}")
            return
            
        self.notifications = notifications
        self.status_label.config(text=f"Status: Checked successfully at {self.last_checked.strftime('%H:%M:%S')}")
        
        # Clear loading/existing items in the frame
        for child in self.list_frame.winfo_children():
            child.destroy()
            
        if not self.notifications:
            empty_lbl = ttk.Label(self.list_frame, text="No notifications found on page.", style="Title.TLabel", foreground="#94a3b8")
            empty_lbl.pack(expand=True)
            return

        # Show notification cards
        for idx, notif in enumerate(self.notifications):
            # Create a card frame for each notification
            card = tk.Frame(self.list_frame, bg="#1e293b", highlightbackground="#334155", highlightcolor="#38bdf8", highlightthickness=1, bd=0)
            card.pack(fill="x", pady=6, ipady=8, ipadx=10)
            
            # First row: No, Type, Date
            top_row = tk.Frame(card, bg="#1e293b")
            top_row.pack(fill="x", padx=10, pady=(5, 2))
            
            no_lbl = ttk.Label(top_row, text=notif['no'], style="CardNo.TLabel")
            no_lbl.pack(side="left")
            
            type_lbl = ttk.Label(top_row, text=f" {notif['type']} ", style="CardType.TLabel")
            type_lbl.pack(side="left", padx=10)
            
            date_lbl = ttk.Label(top_row, text=notif['date'], style="CardDate.TLabel")
            date_lbl.pack(side="right")
            
            # Second row: Subject
            subj_row = tk.Frame(card, bg="#1e293b")
            subj_row.pack(fill="x", padx=10, pady=(5, 5))
            
            subj_lbl = ttk.Label(subj_row, text=notif['subject'], style="CardSubject.TLabel", wraplength=550, justify="left")
            subj_lbl.pack(side="left", anchor="w")
            
            # Right side of card: Actions (Open / Download PDF)
            action_frame = tk.Frame(card, bg="#1e293b")
            action_frame.pack(side="right", fill="y", padx=10, pady=(0, 5))
            
            if notif['link']:
                pdf_link = notif['link']
                # Create visual buttons inside card
                open_btn = tk.Button(action_frame, text="🌐 Open Link", bg="#334155", fg="#ffffff", font=("Segoe UI", 8, "bold"), bd=0, padx=8, pady=4, cursor="hand2", command=lambda link=pdf_link: webbrowser.open(link))
                open_btn.pack(side="left", padx=3)
                
                down_btn = tk.Button(action_frame, text="📥 Download PDF", bg="#2563eb", fg="#ffffff", font=("Segoe UI", 8, "bold"), bd=0, padx=8, pady=4, cursor="hand2", command=lambda link=pdf_link, title=notif['no']: self.download_pdf(link, title))
                down_btn.pack(side="left", padx=3)
            else:
                no_link_lbl = ttk.Label(action_frame, text="No PDF available", style="CardDate.TLabel")
                no_link_lbl.pack(side="right", padx=10)
                
        # Trigger desktop alert/toast if there is a new update
        if is_new_update:
            new_notif = self.notifications[0] if self.notifications else None
            self.show_new_update_popup(new_notif)

    def download_pdf(self, url, title):
        # Format a clean default filename
        clean_title = "".join(c for c in title if c.isalnum() or c in ('-', '_')).rstrip()
        default_filename = f"FBR_Notification_{clean_title}.pdf"
        
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")], initialfile=default_filename)
        
        if not file_path:
            return
            
        self.status_label.config(text=f"Status: Downloading PDF...")
        
        def download_worker():
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, context=ctx) as response, open(file_path, 'wb') as out_file:
                    out_file.write(response.read())
                    
                self.root.after(0, lambda: self.status_label.config(text=f"Status: Downloaded successfully to {os.path.basename(file_path)}"))
                self.root.after(0, lambda: messagebox.showinfo("Download Complete", "The PDF has been downloaded successfully."))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Download Error", f"Failed to download PDF:\n{e}"))
                self.root.after(0, lambda: self.status_label.config(text=f"Status: Download failed"))
                
        threading.Thread(target=download_worker, daemon=True).start()

    def show_new_update_popup(self, new_notif=None):
        # Create a beautiful custom popup window that appears briefly (toast)
        toast = tk.Toplevel(self.root)
        toast.title("New Notification Posted!")
        toast.geometry("450x180+40+40") # Slightly larger to fit the subject
        toast.configure(bg="#1e1b4b") # Deep indigo alert bg
        toast.overrideredirect(True) # Borderless window
        toast.attributes("-topmost", True)
        
        # Title
        lbl1 = tk.Label(toast, text="🔔 New FBR Notification Posted!", bg="#1e1b4b", fg="#a5b4fc", font=("Segoe UI", 10, "bold"))
        lbl1.pack(anchor="w", padx=15, pady=(15, 5))
        
        # Body containing subject/details
        text_content = "A new update has been posted on HRMS FBR!"
        if new_notif:
            text_content = f"Notification No: {new_notif['no']}\nType: {new_notif['type']}\n\nSubject: {new_notif['subject']}"
            
        lbl2 = tk.Label(toast, text=text_content, bg="#1e1b4b", fg="#ffffff", font=("Segoe UI", 9), justify="left", wraplength=420)
        lbl2.pack(anchor="w", padx=15, pady=(0, 10))
        
        close_btn = tk.Button(toast, text="Dismiss", bg="#312e81", fg="#ffffff", bd=0, padx=12, pady=4, cursor="hand2", command=toast.destroy)
        close_btn.pack(side="right", padx=15, pady=(0, 10))
        
        # Audio alert (default system sound)
        self.root.bell()
        
        # Auto-destroy after 12 seconds
        self.root.after(12000, lambda: toast.destroy() if toast.winfo_exists() else None)

    def start_timer_thread(self):
        self.next_update_time = time.time() + (self.update_interval_minutes * 60)
        self.timer_thread = threading.Thread(target=self.timer_worker, daemon=True)
        self.timer_thread.start()

    def timer_worker(self):
        while not self.stop_timer_event.is_set():
            now = time.time()
            remaining = self.next_update_time - now
            
            if remaining <= 0:
                # Trigger update
                self.root.after(0, self.trigger_check)
                # Next run calculated during trigger / callback
                time.sleep(2)
                continue
                
            # Update GUI countdown display
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            
            # Simple format: HH:MM:SS or MM:SS
            timer_text = f"Next update in: {mins:02d}m {secs:02d}s"
            self.root.after(0, lambda txt=timer_text: self.timer_label.config(text=txt))
            
            # Sleep 1 second
            self.stop_timer_event.wait(1.0)

    def on_close(self):
        self.stop_timer_event.set()
        self.root.destroy()
        sys.exit()

    def add_to_startup(self):
        try:
            if getattr(sys, 'frozen', False):
                app_path = os.path.abspath(sys.executable)
            else:
                app_path = os.path.abspath(sys.argv[0])
                
            startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
            shortcut_path = os.path.join(startup_dir, "FBRNotificationMonitor.lnk")
            
            if not os.path.exists(shortcut_path):
                import subprocess
                ps_script = f'$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut("{shortcut_path}"); $Shortcut.TargetPath = "{app_path}"; $Shortcut.WorkingDirectory = "{os.path.dirname(app_path)}"; $Shortcut.Save()'
                subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script], capture_output=True)
        except Exception as e:
            print("Failed to add to Windows Startup:", e)

if __name__ == "__main__":
    # Disable HTTPS certificate validation warning just in case
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context
        
    root = tk.Tk()
    app = FBRMonitorApp(root)
    root.mainloop()
