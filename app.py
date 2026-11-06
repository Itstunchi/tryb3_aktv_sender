"""A local-only, demo-mode email sender prototype."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from urllib.parse import parse_qs
import json
from pathlib import Path

ROOT = Path(__file__).parent
STATE = ROOT / "state.json"
DEFAULT = {"contacts": [], "events": []}


def read_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT.copy()


def save(state):
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def page():
    s = read_state()
    contacts = "".join(f'<option value="{escape(c["email"], quote=True)}">{escape(c["name"])} — {escape(c["email"])} (consented)</option>' for c in s["contacts"])
    events = "".join(f'<tr><td>{escape(e["time"])}</td><td>{escape(e["to"])}</td><td><b class="{escape(e["kind"])}">{escape(e["status"])}</b></td><td>{escape(e["detail"])}</td></tr>' for e in reversed(s["events"][-30:])) or '<tr><td colspan="4" class="muted">No events yet. Try demo send.</td></tr>'
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sender — local preview</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f3f5f7;color:#17212b;font:15px system-ui}}header{{background:#102b3f;color:white;padding:20px max(24px,calc((100% - 1180px)/2));display:flex;justify-content:space-between;align-items:center}}main{{max-width:1180px;margin:24px auto;padding:0 20px}}h1{{font-size:20px;margin:0}}h2{{font-size:17px;margin:0 0 14px}}.badge{{background:#c4f0dd;color:#075c3d;padding:5px 10px;border-radius:20px;font-size:12px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.card{{background:white;border:1px solid #dce3e8;border-radius:12px;padding:20px;margin-bottom:18px;box-shadow:0 2px 8px #152f3b08}}label{{display:block;font-weight:600;font-size:13px;margin:12px 0 6px}}input,textarea,select{{width:100%;border:1px solid #cbd5dc;border-radius:7px;padding:10px;font:inherit}}textarea{{min-height:150px;resize:vertical}}button{{border:0;border-radius:7px;background:#087e68;color:white;padding:10px 15px;font-weight:650;cursor:pointer;margin-top:12px}}button.alt{{background:#e9eff2;color:#193142}}.muted{{color:#6d7c86;font-size:13px}}.notice{{background:#fff8e5;border:1px solid #f1d690;border-radius:8px;padding:11px 13px;color:#69521c;font-size:13px;margin-bottom:18px}}.preview{{border:1px solid #dce3e8;border-radius:9px;overflow:hidden;min-height:280px}}.mailhead{{padding:12px 15px;background:#f5f8fa;border-bottom:1px solid #e1e8ec;font-size:13px}}.mailbody{{padding:20px;line-height:1.55;overflow-wrap:anywhere}}.mailbody img{{max-width:100%;height:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}td,th{{text-align:left;padding:10px 8px;border-bottom:1px solid #e9eef1}}th{{color:#60717c}}.success{{color:#08704f}}.failed{{color:#bd3d36}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}header{{padding:16px 20px}}}}</style></head><body>
<header><h1>✉ Sender <span style="font-weight:400;color:#b9cbd5">/ local preview</span></h1><span class="badge">DEMO MODE · no email leaves this device</span></header><main><div class="notice"><b>Safe preview:</b> Sends are simulated and recorded locally. Add only people who agreed to receive messages. SMTP acceptance (when added) cannot confirm inbox delivery.</div>
<div class="grid"><section><div class="card"><h2>Compose</h2><form method="post" action="/send" enctype="application/x-www-form-urlencoded"><label>To (consented contacts only)</label><select name="to" required>{contacts}<option value="" disabled selected>Select a saved contact</option></select><p class="muted">Add a contact with recorded permission below. No bulk import in this preview.</p><label>Subject</label><input id="subject" name="subject" placeholder="A note for you" maxlength="180" required><label>Message</label><textarea id="body" name="body" placeholder="Write your message…" required></textarea><label>Attachment preview (local file name only in demo)</label><input id="attachment" name="attachment" type="file" accept="image/*,.pdf"><button type="submit">Run demo send</button></form></div>
<div class="card"><h2>Contact book</h2><form method="post" action="/contact"><label>Name</label><input name="name" required maxlength="80"><label>Email</label><input name="email" type="email" required maxlength="254"><label style="display:flex;gap:8px;align-items:center;font-weight:500"><input style="width:auto" type="checkbox" name="consent" required> I recorded this person’s permission to receive messages</label><button class="alt" type="submit">Save contact</button></form></div></section>
<section><div class="card"><h2>Recipient preview</h2><div class="preview"><div class="mailhead"><div><b>From:</b> You &lt;you@example.test&gt;</div><div><b>To:</b> <span id="pvto">Choose a contact</span></div><div><b>Subject:</b> <span id="pvsubject">Your subject appears here</span></div></div><div class="mailbody" id="pvbody">Your message preview appears here.</div><div class="mailhead muted" id="pvfile">No attachment</div></div><p class="muted">Text is previewed as plain text; actual client rendering varies. HTML composition and sending integrations are next steps.</p></div>
<div class="card"><h2>Recent activity</h2><table><thead><tr><th>Time</th><th>Recipient</th><th>Result</th><th>Details</th></tr></thead><tbody>{events}</tbody></table><p class="muted">“Demo accepted” is simulated, not a real delivery receipt.</p></div></section></div></main>
<script>const $=s=>document.querySelector(s);$('#subject').oninput=()=>$('#pvsubject').textContent=$('#subject').value||'Your subject appears here';$('#body').oninput=()=>$('#pvbody').textContent=$('#body').value||'Your message preview appears here.';document.querySelector('select').onchange=e=>$('#pvto').textContent=e.target.value;$('#attachment').onchange=e=>$('#pvfile').textContent=e.target.files[0]?.name||'No attachment';</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_error(404); return
        body = page().encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size > 20000:
            self.send_error(413); return
        form = parse_qs(self.rfile.read(size).decode("utf-8", "replace"))
        val = lambda key: form.get(key, [""])[0].strip()
        s = read_state()
        if self.path == "/contact":
            email = val("email").lower()
            if val("consent") and "@" in email and not any(c["email"] == email for c in s["contacts"]):
                s["contacts"].append({"name": val("name")[:80], "email": email})
        elif self.path == "/send":
            recipient = val("to")
            if any(c["email"] == recipient for c in s["contacts"]) and val("subject") and val("body"):
                from datetime import datetime, timezone
                s["events"].append({"time": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"), "to": recipient, "status": "Demo accepted", "kind": "success", "detail": "Simulated locally; no message sent."})
        else:
            self.send_error(404); return
        save(s); self.send_response(303); self.send_header("Location", "/"); self.end_headers()

    def log_message(self, fmt, *args):
        print("[http]", fmt % args)


if __name__ == "__main__":
    print("Sender demo at http://127.0.0.1:8765 (local only)")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
