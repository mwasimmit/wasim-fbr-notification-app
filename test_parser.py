import urllib.request
import urllib.parse
from html.parser import HTMLParser
import ssl

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

def test_fetch():
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
        
        print(f"Parsed {len(parser.notifications)} notifications:")
        for idx, notif in enumerate(parser.notifications[:5]):
            print(f"\n[{idx+1}] No: {notif['no']}")
            print(f"    Type: {notif['type']}")
            print(f"    Subject: {notif['subject']}")
            print(f"    Date: {notif['date']}")
            print(f"    Link: {notif['link']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_fetch()
