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

# Standard Library/External modules for system tray support
try:
    from PIL import Image, ImageDraw
    import pystray
    TRAY_SUPPORT = True
except ImportError:
    TRAY_SUPPORT = False

# Helper function to dynamically generate a system tray icon with optional badge count
def create_tray_icon_image(count=0):
    if not TRAY_SUPPORT:
        return None
    try:
        # Generate a simple 64x64 icon image
        image = Image.new('RGBA', (64, 64), color=(15, 23, 42, 255)) # Dark slate bg
        dc = ImageDraw.Draw(image)
        # Draw a blue notification circle
        dc.ellipse([8, 8, 56, 56], fill=(37, 99, 235, 255), outline=(56, 189, 248, 255), width=2)
        # Draw a simple bell symbol
        dc.polygon([(32, 16), (20, 42), (44, 42)], fill=(255, 255, 255, 255))
        dc.ellipse([28, 42, 36, 50], fill=(255, 255, 255, 255))
        # Draw badge with notification count
        if count > 0:
            # Red badge circle in top-right corner
            dc.ellipse([38, 2, 62, 26], fill=(239, 68, 68, 255), outline=(255, 255, 255, 255), width=1)
            badge_text = str(count) if count <= 9 else "9+"
            try:
                from PIL import ImageFont
                font = ImageFont.truetype("arial.ttf", 13)
            except Exception:
                font = ImageFont.load_default()
            bbox = dc.textbbox((0, 0), badge_text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            dc.text((50 - tw // 2, 14 - th // 2), badge_text, fill=(255, 255, 255, 255), font=font)
        return image
    except Exception:
        return None

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
        self.root.geometry("880x660")
        self.root.minsize(780, 520)
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
        self.tray_icon = None
        self.new_notification_count = 0  # Badge count for tray icon
        
        # Configure styles
        self.setup_styles()
        
        # Setup Window Menus
        self.setup_menu()
        
        # Build UI layout
        self.build_ui()
        
        # Create desktop & start menu shortcuts on first run
        self.create_desktop_and_startmenu_shortcuts()
        
        # Initial check
        self.trigger_check()
        
        # Start background timer
        self.start_timer_thread()
        
        # Handle close & minimize events
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_clicked)
        self.root.bind("<Unmap>", self.on_minimize)

    def setup_menu(self):
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about_dialog)

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
        interval_label = ttk.Label(control_frame, text="Interval: ", style="Subtitle.TLabel")
        interval_label.pack(side="left", padx=(0, 5))
        
        self.interval_var = tk.StringVar(value="1 Hour")
        intervals = ["5 Minutes", "15 Minutes", "30 Minutes", "1 Hour", "2 Hours", "6 Hours"]
        self.interval_menu = ttk.Combobox(control_frame, textvariable=self.interval_var, values=intervals, width=12, state="readonly")
        self.interval_menu.pack(side="left", padx=5)
        self.interval_menu.bind("<<ComboboxSelected>>", self.on_interval_changed)
        
        # Windows Startup Checkbox
        self.startup_var = tk.BooleanVar()
        self.check_startup_status()
        self.startup_cb = tk.Checkbutton(
            control_frame, 
            text="Run on Startup", 
            variable=self.startup_var, 
            onvalue=True, 
            offvalue=False,
            command=self.toggle_startup,
            bg="#0f172a",
            fg="#94a3b8",
            selectcolor="#1e293b",
            activebackground="#0f172a",
            activeforeground="#f8fafc",
            font=("Segoe UI", 9)
        )
        self.startup_cb.pack(side="left", padx=15)
        
        # Manual Refresh Button
        self.refresh_btn = ttk.Button(control_frame, text="🔄 Refresh Now", style="Primary.TButton", command=self.trigger_check)
        self.refresh_btn.pack(side="left", padx=10)
        
        # Timer / Status Text
        self.timer_label = ttk.Label(control_frame, text="Next update in: Calculating...", style="Timer.TLabel")
        self.timer_label.pack(side="right", padx=10)
        
        # --- Divider Line ---
        divider = tk.Frame(self.root, height=1, bg="#334155")
        divider.pack(fill="x", padx=20, pady=5)
        
        # --- Main Notification List Panel with Scrollable Canvas ---
        self.list_frame = ttk.Frame(self.root, padding=(20, 5))
        self.list_frame.pack(fill="both", expand=True)
        
        # Canvas & Scrollbar setup for modern scrolling
        self.canvas = tk.Canvas(self.list_frame, bg="#0f172a", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#0f172a")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Mousewheel scroll binding
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Inline connection warning label (hidden by default)
        self.error_banner = tk.Frame(self.scrollable_frame, bg="#7f1d1d", padx=15, pady=8, highlightbackground="#f87171", highlightthickness=1)
        self.error_lbl = tk.Label(self.error_banner, text="⚠️ Connection Offline: Unable to sync with FBR website. Retrying automatically.", bg="#7f1d1d", fg="#fca5a5", font=("Segoe UI", 10, "bold"))
        self.error_lbl.pack(anchor="w")

        # Loading Indicator inside scroll area
        self.loading_label = ttk.Label(self.scrollable_frame, text="Loading updates...", style="Title.TLabel", foreground="#94a3b8")
        self.loading_label.pack(pady=40)
        
        # --- Bottom Status bar ---
        status_bar = ttk.Frame(self.root, padding=(10, 5))
        status_bar.pack(fill="x", side="bottom")
        
        self.status_label = ttk.Label(status_bar, text="Status: Ready", style="Status.TLabel")
        self.status_label.pack(side="left")
        
        # Link to source page
        source_label = ttk.Label(status_bar, text="Source Page (HRMS FBR)", foreground="#38bdf8", cursor="hand2", font=("Segoe UI", 9, "underline"))
        source_label.pack(side="right")
        source_label.bind("<Button-1>", lambda e: webbrowser.open("https://hrms.fbr.gov.pk/eposting/Proposal/SearchNotification.aspx?view=ExternalLink"))

    def check_startup_status(self):
        startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_dir, "FBRNotificationMonitor.lnk")
        self.startup_var.set(os.path.exists(shortcut_path))

    def toggle_startup(self):
        startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_dir, "FBRNotificationMonitor.lnk")
        if self.startup_var.get():
            self.add_to_startup()
        else:
            try:
                if os.path.exists(shortcut_path):
                    os.remove(shortcut_path)
                    self.status_label.config(text="Status: Removed from Windows Startup")
            except Exception as e:
                self.status_label.config(text="Status: Failed to remove startup link")

    def show_about_dialog(self):
        about_win = tk.Toplevel(self.root)
        about_win.title("About FBR Notification Monitor")
        about_win.geometry("450x300")
        about_win.configure(bg="#1e293b")
        about_win.resizable(False, False)
        about_win.transient(self.root)
        about_win.grab_set()
        
        # Center the window
        about_win.geometry("+%d+%d" % (self.root.winfo_x() + 150, self.root.winfo_y() + 100))
        
        title = tk.Label(about_win, text="FBR Notification Monitor", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 14, "bold"))
        title.pack(pady=(20, 10))
        
        details = (
            "Developed By: Muhammad Wasim\n"
            "Email: mwasimmit@gmail.com\n\n"
            "About the Developer:\n"
            "I am a hobbyist developer who built this app\n"
            "out of fun and curiosity to track official postings."
        )
        
        info_lbl = tk.Label(about_win, text=details, bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 10), justify="center")
        info_lbl.pack(pady=(5, 5))

        # Add LinkedIn Link
        linkedin_lbl = tk.Label(
            about_win, 
            text="LinkedIn: https://www.linkedin.com/in/mwasimmit/", 
            bg="#1e293b", 
            fg="#38bdf8", 
            font=("Segoe UI", 9, "underline"), 
            cursor="hand2"
        )
        linkedin_lbl.pack(pady=(5, 10))
        linkedin_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://www.linkedin.com/in/mwasimmit/"))
        
        btn = tk.Button(about_win, text="Close", bg="#2563eb", fg="#ffffff", font=("Segoe UI", 9, "bold"), bd=0, padx=20, pady=6, cursor="hand2", command=about_win.destroy)
        btn.pack(pady=(5, 15))

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
        self.next_update_time = time.time() + (self.update_interval_minutes * 60)

    def trigger_check(self):
        if self.is_checking:
            return
        
        self.is_checking = True
        self.status_label.config(text="Status: Checking.")
        self.refresh_btn.state(["disabled"])
        
        # Start dot animation
        self.animate_checking()
        
        # Run parsing in background thread to avoid freezing GUI
        threading.Thread(target=self.fetch_notifications_worker, daemon=True).start()

    def animate_checking(self):
        if not self.is_checking:
            return
        current_text = self.status_label.cget("text")
        if "Checking" in current_text:
            dots = current_text.count(".")
            new_dots = (dots % 3) + 1
            self.status_label.config(text=f"Status: Checking{'.' * new_dots}")
        self.root.after(500, self.animate_checking)

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
            
            top_5 = parser.notifications[:10]
            
            # Check if there is any new update
            is_new_update = False
            if top_5 and self.latest_seen_no:
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
        
        # Clear loading label
        self.loading_label.pack_forget()
        
        if error:
            # Inline error handling banner (No blocking message box)
            self.status_label.config(text=f"Status: Offline (Last check: {self.last_checked.strftime('%H:%M:%S')})")
            self.error_banner.pack(fill="x", pady=10, before=self.loading_label)
            return
            
        # Hide the error banner if connection succeeded
        self.error_banner.pack_forget()
        self.notifications = notifications
        self.status_label.config(text=f"Status: Checked successfully at {self.last_checked.strftime('%H:%M:%S')}")
        
        # Clear existing card items
        for child in self.scrollable_frame.winfo_children():
            if child != self.error_banner and child != self.loading_label:
                child.destroy()
            
        if not self.notifications:
            empty_lbl = ttk.Label(self.scrollable_frame, text="No notifications found on page.", style="Title.TLabel", foreground="#94a3b8")
            empty_lbl.pack(pady=40)
            return

        # Show notification cards
        for idx, notif in enumerate(self.notifications):
            card = tk.Frame(self.scrollable_frame, bg="#1e293b", highlightbackground="#334155", highlightcolor="#38bdf8", highlightthickness=1, bd=0)
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
            
            subj_lbl = ttk.Label(subj_row, text=notif['subject'], style="CardSubject.TLabel", wraplength=520, justify="left")
            subj_lbl.pack(side="left", anchor="w")
            
            # Right side: Actions
            action_frame = tk.Frame(card, bg="#1e293b")
            action_frame.pack(side="right", fill="y", padx=10, pady=(0, 5))
            
            if notif['link']:
                pdf_link = notif['link']
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
            self.new_notification_count += 1
            self.update_tray_icon_badge()
            self.show_new_update_popup(new_notif)

    def download_pdf(self, url, title):
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
        toast.geometry("450x180+40+40") 
        toast.configure(bg="#1e1b4b") 
        toast.overrideredirect(True) 
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
        
        # Audio alert
        self.root.bell()
        
        # Make the popup actionable - Click to restore app
        toast.bind("<Button-1>", lambda e: self.restore_from_tray())
        lbl1.bind("<Button-1>", lambda e: self.restore_from_tray())
        lbl2.bind("<Button-1>", lambda e: self.restore_from_tray())
        
        self.root.after(30000, lambda: toast.destroy() if toast.winfo_exists() else None)

    def on_minimize(self, event=None):
        # Trigger tray minimization only if minimized state is active
        if self.root.state() == 'iconic':
            self.minimize_to_tray()

    def on_close_clicked(self):
        # Minimize to tray instead of quitting directly
        self.minimize_to_tray()

    def setup_tray(self):
        if not TRAY_SUPPORT:
            return
        
        # Avoid creating duplicate icons
        if self.tray_icon:
            return
            
        image = create_tray_icon_image(self.new_notification_count)
        if not image:
            return
            
        from pystray import MenuItem as item
        menu = (
            item('Open Monitor', lambda: self.restore_from_tray(), default=True),
            item('Check Now', lambda: self.root.after(0, self.trigger_check)),
            item('Exit App', lambda: self.exit_app())
        )
        tooltip = "FBR Notification Monitor"
        if self.new_notification_count > 0:
            tooltip = f"FBR Monitor - {self.new_notification_count} new notification(s)"
        self.tray_icon = pystray.Icon("fbrmonitor", image, tooltip, menu)

    def minimize_to_tray(self):
        if not TRAY_SUPPORT:
            self.root.withdraw()
            return
            
        self.root.withdraw()
        self.setup_tray()
        if self.tray_icon:
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def update_tray_icon_badge(self):
        """Update the tray icon image to reflect the current notification count."""
        if TRAY_SUPPORT and self.tray_icon:
            new_image = create_tray_icon_image(self.new_notification_count)
            if new_image:
                self.tray_icon.icon = new_image
                if self.new_notification_count > 0:
                    self.tray_icon.title = f"FBR Monitor - {self.new_notification_count} new notification(s)"
                else:
                    self.tray_icon.title = "FBR Notification Monitor"

    def restore_from_tray(self, icon=None):
        # Reset notification count when app is opened
        self.new_notification_count = 0
        if TRAY_SUPPORT and self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.after(0, self.root.deiconify)
        self.root.after(0, lambda: self.root.state('normal'))
        self.root.after(0, self.root.focus_force)

    def start_timer_thread(self):
        self.next_update_time = time.time() + (self.update_interval_minutes * 60)
        self.timer_thread = threading.Thread(target=self.timer_worker, daemon=True)
        self.timer_thread.start()

    def timer_worker(self):
        while not self.stop_timer_event.is_set():
            now = time.time()
            remaining = self.next_update_time - now
            
            if remaining <= 0:
                self.root.after(0, self.trigger_check)
                time.sleep(2)
                continue
                
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            
            timer_text = f"Next update in: {mins:02d}m {secs:02d}s"
            self.root.after(0, lambda txt=timer_text: self.timer_label.config(text=txt))
            
            self.stop_timer_event.wait(1.0)

    def _get_app_path(self):
        """Return the absolute path to the running executable or script."""
        if getattr(sys, 'frozen', False):
            return os.path.abspath(sys.executable)
        return os.path.abspath(sys.argv[0])

    def _create_shortcut(self, shortcut_path, app_path, description="FBR Notification Monitor"):
        """Create a Windows .lnk shortcut using PowerShell/WScript.Shell."""
        import subprocess
        ps_script = (
            f'$WshShell = New-Object -ComObject WScript.Shell; '
            f'$Shortcut = $WshShell.CreateShortcut("{shortcut_path}"); '
            f'$Shortcut.TargetPath = "{app_path}"; '
            f'$Shortcut.WorkingDirectory = "{os.path.dirname(app_path)}"; '
            f'$Shortcut.Description = "{description}"; '
            f'$Shortcut.Save()'
        )
        subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script], capture_output=True)

    def create_desktop_and_startmenu_shortcuts(self):
        """Create Desktop and Start Menu shortcuts on first run so the user can launch the app manually."""
        try:
            app_path = self._get_app_path()
            shortcut_name = "FBR Notification Monitor.lnk"

            # Desktop shortcut
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            desktop_shortcut = os.path.join(desktop_dir, shortcut_name)
            if not os.path.exists(desktop_shortcut):
                self._create_shortcut(desktop_shortcut, app_path)

            # Start Menu shortcut (user-level Programs folder)
            start_menu_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs")
            start_menu_shortcut = os.path.join(start_menu_dir, shortcut_name)
            if not os.path.exists(start_menu_shortcut):
                self._create_shortcut(start_menu_shortcut, app_path)

        except Exception:
            pass  # Non-critical — don't block the app

    def add_to_startup(self):
        try:
            app_path = self._get_app_path()
                
            startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
            shortcut_path = os.path.join(startup_dir, "FBRNotificationMonitor.lnk")
            
            if not os.path.exists(shortcut_path):
                self._create_shortcut(shortcut_path, app_path)
                self.status_label.config(text="Status: Added to Windows Startup successfully")
        except Exception as e:
            self.status_label.config(text="Status: Failed to register Windows Startup")

    def exit_app(self):
        self.stop_timer_event.set()
        if TRAY_SUPPORT and self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context
        
    root = tk.Tk()
    app = FBRMonitorApp(root)
    root.mainloop()
