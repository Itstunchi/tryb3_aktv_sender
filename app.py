
#!/usr/bin/env python3
"""
TermSender Pro Web Application
Professional email sender with SMTP rotation and advanced analytics
"""

import os
import json
import smtplib
import time
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional
import tempfile
import uuid
import functools
import secrets
import mimetypes
import copy
import csv

from flask import Flask, render_template, request, jsonify, session, send_file, redirect, url_for, flash, abort, g
from werkzeug.utils import secure_filename
from email_validator import validate_email, EmailNotValidError
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Import our enhanced classes
from config_manager import config_manager
from termsender import SMTPRotationManager, AnalyticsManager, SMTPServer
from account_store import store as account_store, DATA_DIR

app = Flask(__name__)
ADMIN_RECOVERY_EMAIL = 'xexplatform@gmail.com'
app.secret_key = os.environ.get('SESSION_SECRET') or secrets.token_urlsafe(32)
if os.environ.get('APP_ENV') == 'production' and not os.environ.get('SESSION_SECRET'):
    raise RuntimeError('SESSION_SECRET is required in production')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.environ.get('APP_ENV') == 'production',
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Configuration
UPLOAD_FOLDER = Path('uploads')
UPLOAD_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {'txt', 'csv', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'doc', 'docx'}
SEND_JOBS = {}
SEND_JOBS_LOCK = threading.Lock()


@app.before_request
def protect_csrf():
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        expected = session.get('csrf_token', '')
        supplied = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
        if not expected or not secrets.compare_digest(expected, supplied):
            return jsonify({'success': False, 'message': 'Security token expired. Refresh and try again.'}), 400


@app.context_processor
def inject_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return {'csrf_token_value': session['csrf_token']}


@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.endpoint not in {'static'}:
        response.headers['Cache-Control'] = 'no-store'
    return response


def _run_send_job(job_id, sender, content, recipients, attachments, dry_run, delay_between_emails):
    def record_progress(snapshot):
        with SEND_JOBS_LOCK:
            job = SEND_JOBS.get(job_id)
            if job is not None:
                job['results'] = copy.deepcopy(snapshot)

    try:
        result = sender.send_emails_async(
            content=content,
            recipients=recipients,
            attachments=attachments,
            dry_run=dry_run,
            progress_callback=record_progress,
            delay_between_emails=delay_between_emails,
        )
        with SEND_JOBS_LOCK:
            SEND_JOBS[job_id].update(status='complete', results=result)
    except Exception as exc:
        with SEND_JOBS_LOCK:
            SEND_JOBS[job_id].update(status='failed', error=str(exc))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def user_upload_folder(user_id):
    path = DATA_DIR / 'uploads' / str(int(user_id))
    path.mkdir(parents=True, exist_ok=True)
    return path

def user_analytics_file(user_id):
    path = DATA_DIR / 'users' / str(int(user_id)) / 'analytics' / 'campaign_analytics.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def validate_email_address(email):
    """Validate email address"""
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False

class WebEmailSender:
    """Web-optimized email sender with SMTP rotation"""

    def __init__(self, smtp_configs: List[dict], rotation_mode: str = "email_count", rotation_value: int = 10, analytics_file=None):
        # Convert dicts to SMTPServer objects
        smtp_servers = []
        for config in smtp_configs:
            server = SMTPServer(
                name=config['name'],
                host=config['host'],
                port=config['port'],
                username=config['username'],
                password=config['password'],
                sender_email=config['sender_email'],
                use_tls=config.get('use_tls', True),
                use_ssl=config.get('use_ssl', False),
                enabled=config.get('enabled', True)
            )
            smtp_servers.append(server)
        
        self.smtp_manager = SMTPRotationManager(smtp_servers, rotation_mode, rotation_value)
        self.analytics = AnalyticsManager(analytics_file=analytics_file)

    def send_emails_async(self, content: dict, recipients: List[str], attachments: List[str] = None, 
                         dry_run: bool = False, progress_callback=None, delay_between_emails: float = 1.0):
        """Send emails with SMTP rotation and progress updates"""
        
        campaign_id = f"web_campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        stats = self.analytics.start_campaign(campaign_id, len(recipients))
        
        results = {
            "sent": 0,
            "failed": 0,
            "failed_recipients": [],
            "start_time": datetime.now().isoformat(),
            "total": len(recipients),
            "dry_run": dry_run,
            "smtp_rotations": 0,
            "smtp_usage": {},
            "current_smtp": "",
            "activity": []
        }

        if dry_run:
            for i, recipient in enumerate(recipients):
                # Simulate SMTP rotation for demo
                if self.smtp_manager.should_rotate():
                    server = self.smtp_manager.rotate_server()
                    results["smtp_rotations"] += 1
                    results["current_smtp"] = server.name
                
                current_server = self.smtp_manager.get_current_server()
                results["current_smtp"] = current_server.name
                
                # Update usage stats
                if current_server.name not in results["smtp_usage"]:
                    results["smtp_usage"][current_server.name] = 0
                results["smtp_usage"][current_server.name] += 1
                
                self.smtp_manager.record_email_sent()
                results["sent"] = i + 1
                results["activity"].append({
                    "timestamp": datetime.now().isoformat(),
                    "email": recipient,
                    "subject": content.get('subject', ''),
                    "smtp_server": self.smtp_manager.get_current_server().name,
                    "status": "sent",
                    "error": None
                })
                time.sleep(0.1)  # Simulate processing
                
                if progress_callback:
                    progress_callback(results)
            
            results["end_time"] = datetime.now().isoformat()
            self.analytics.end_campaign()
            return results

        try:
            for i, recipient in enumerate(recipients):
                try:
                    # Check if we should rotate SMTP servers
                    if self.smtp_manager.should_rotate():
                        new_server = self.smtp_manager.rotate_server()
                        results["smtp_rotations"] += 1
                        results["current_smtp"] = new_server.name
                        self.analytics.record_smtp_rotation()
                    
                    current_server = self.smtp_manager.get_current_server()
                    results["current_smtp"] = current_server.name
                    
                    # Get SMTP connection
                    server_connection = self.smtp_manager.get_server_connection(current_server)
                    
                    # Create message
                    msg = MIMEMultipart('mixed')
                    msg['From'] = current_server.sender_email
                    msg['To'] = recipient
                    msg['Subject'] = content['subject']

                    # Add body
                    body_type = 'html' if content.get('is_html', False) else 'plain'
                    inline_files = [a for a in (attachments or []) if a.get('inline') and a.get('id') and f"cid:{a['id']}" in content.get('body', '')]
                    if body_type == 'html' and inline_files:
                        related = MIMEMultipart('related')
                        related.attach(MIMEText(content['body'], 'html', 'utf-8'))
                        for metadata in inline_files:
                            media_type, _ = mimetypes.guess_type(metadata['path'])
                            main_type, sub_type = (media_type or 'application/octet-stream').split('/', 1)
                            with open(metadata['path'], 'rb') as image_file:
                                part = MIMEBase(main_type, sub_type)
                                part.set_payload(image_file.read())
                            encoders.encode_base64(part)
                            part.add_header('Content-ID', f"<{metadata['id']}>")
                            part.add_header('Content-Disposition', 'inline', filename=os.path.basename(metadata['path']))
                            related.attach(part)
                        msg.attach(related)
                    else:
                        msg.attach(MIMEText(content['body'], body_type, 'utf-8'))

                    # Add attachments
                    if attachments:
                        for attachment in attachments:
                            if attachment.get('inline') and attachment in inline_files:
                                continue
                            attachment_path = attachment['path']
                            if os.path.exists(attachment_path):
                                with open(attachment_path, "rb") as attachment:
                                    part = MIMEBase('application', 'octet-stream')
                                    part.set_payload(attachment.read())

                                encoders.encode_base64(part)
                                part.add_header(
                                    'Content-Disposition',
                                    f'attachment; filename= {os.path.basename(attachment_path)}'
                                )
                                msg.attach(part)

                    # Send email
                    refused = server_connection.sendmail(
                        current_server.sender_email,
                        recipient,
                        msg.as_string()
                    )
                    if refused:
                        raise RuntimeError(f"SMTP rejected recipient: {refused}")

                    # Record success
                    self.smtp_manager.record_email_sent()
                    self.analytics.record_email_sent(current_server.name)
                    results["sent"] += 1
                    results["activity"].append({
                        "timestamp": datetime.now().isoformat(),
                        "email": recipient,
                        "subject": content.get('subject', ''),
                        "smtp_server": current_server.name,
                        "status": "sent",
                        "error": None
                    })
                    
                    # Update usage stats
                    if current_server.name not in results["smtp_usage"]:
                        results["smtp_usage"][current_server.name] = 0
                    results["smtp_usage"][current_server.name] += 1
                    
                    time.sleep(max(1.0, min(float(delay_between_emails), 60.0)))

                except Exception as e:
                    current_server = self.smtp_manager.get_current_server()
                    self.analytics.record_email_failed(recipient, str(e), current_server.name)
                    results["failed"] += 1
                    results["failed_recipients"].append({"email": recipient, "error": str(e)})
                    results["activity"].append({
                        "timestamp": datetime.now().isoformat(),
                        "email": recipient,
                        "subject": content.get('subject', ''),
                        "smtp_server": current_server.name if current_server else "",
                        "status": "failed",
                        "error": str(e)
                    })

                # Update progress
                if progress_callback:
                    progress_callback(results)

            # Cleanup connections
            self.smtp_manager.cleanup_connections()
            results["end_time"] = datetime.now().isoformat()
            self.analytics.end_campaign()

        except Exception as e:
            results["smtp_error"] = str(e)
            results["end_time"] = datetime.now().isoformat()

        return results

# Routes
# Authentication decorator
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        user = account_store.user(session.get('user_id'))
        if not user:
            session.clear()
            return redirect(url_for('login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Sign in to an activated account."""
    if account_store.user(session.get('user_id')):
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        user = account_store.login(request.form.get('email', ''), request.form.get('password', ''))
        if user:
            session.clear()
            session.permanent = True
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            session['is_admin'] = bool(user['is_admin'])
            session['csrf_token'] = secrets.token_urlsafe(32)
            return redirect(url_for('index'))
        error = 'Email or password was not recognized.'
    return render_template('login.html', error=error)


def _send_admin_reset_code(account_email, code):
    server_config = next(
        (
            server for server in config_manager.get_smtp_servers()
            if server.get('enabled')
            and server.get('sender_email', '').strip().lower() == ADMIN_RECOVERY_EMAIL
        ),
        None,
    )
    if not server_config:
        raise RuntimeError('No enabled SMTP server is configured for the recovery mailbox.')

    host = server_config.get('host')
    port = server_config.get('port')
    username = server_config.get('username')
    password = server_config.get('password')
    if not host or not port or not username or not password:
        raise RuntimeError('The recovery SMTP server configuration is incomplete.')

    message = MIMEText(
        f'Your TermSender administrator password reset code is {code}. '
        f'It expires in 10 minutes and applies to {account_email}.',
        'plain',
    )
    message['Subject'] = 'TermSender password reset code'
    message['From'] = ADMIN_RECOVERY_EMAIL
    message['To'] = ADMIN_RECOVERY_EMAIL

    try:
        if server_config.get('use_ssl'):
            connection = smtplib.SMTP_SSL(host, int(port), timeout=20)
        else:
            connection = smtplib.SMTP(host, int(port), timeout=20)
        with connection as smtp:
            if server_config.get('use_tls') and not server_config.get('use_ssl'):
                smtp.starttls()
            smtp.login(username, password)
            refused = smtp.send_message(message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        raise RuntimeError('The recovery email could not be delivered.') from exc


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    message = None
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        code = f'{secrets.randbelow(1_000_000):06d}'
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        if account_store.issue_admin_password_reset(email, code, expires_at):
            try:
                _send_admin_reset_code(email, code)
            except RuntimeError:
                account_store.clear_admin_password_reset(email, code)
                app.logger.exception('Failed to deliver administrator password reset email')
                error = 'Could not send a recovery code. Check the recovery email SMTP settings and try again.'
            else:
                message = 'If this is the administrator account, a code was sent to the recovery mailbox.'
        else:
            message = 'If this is the administrator account, a code was sent to the recovery mailbox.'
    return render_template('forgot_password.html', message=message, error=error)


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        code = request.form.get('code', '').strip()
        password = request.form.get('password', '')
        if len(password) < 12:
            error = 'Use a password with at least 12 characters.'
        elif not account_store.reset_admin_password(email, code, password):
            error = 'The code is invalid or expired. Request a new code and try again.'
        else:
            return render_template('login.html', error=None, message='Password updated. Sign in with your new password.')
    return render_template('reset_password.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        if len(password) < 12:
            error = 'Use a password with at least 12 characters.'
        elif len(email) > 254 or not name or len(name) > 100:
            error = 'Enter a valid email and name.'
        else:
            user, error = account_store.activate(email, name, password, request.form.get('license_key', ''))
            if user:
                session.clear()
                session.permanent = True
                session['user_id'] = user['id']
                session['user_email'] = user['email']
                session['user_name'] = user['name']
                session['is_admin'] = False
                session['csrf_token'] = secrets.token_urlsafe(32)
                return redirect(url_for('index'))
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET'])
@login_required
def admin():
    """Admin page for license key management"""
    # Only allow access if user is admin
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    
    license_keys = account_store.licenses()
    return render_template('admin.html', license_keys=license_keys)

@app.route('/admin/generate-key', methods=['POST'])
@login_required
def admin_generate_key():
    """Generate a new license key"""
    # Only allow access if user is admin
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    
    user_email = request.form.get('user_email')
    user_name = request.form.get('user_name')
    expiry_days = int(request.form.get('expiry_days', 365))
    
    new_key = account_store.issue(user_email, user_name, expiry_days)
    license_keys = account_store.licenses()
    
    return render_template('admin.html', license_keys=license_keys, new_key=new_key)

@app.route('/admin/deactivate-key', methods=['POST'])
@login_required
def admin_deactivate_key():
    """Deactivate a license key"""
    # Only allow access if user is admin
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    
    user_email = request.form.get('user_email')
    account_store.revoke(user_email)
    
    license_keys = account_store.licenses()
    return render_template('admin.html', license_keys=license_keys)

@app.route('/')
@login_required
def index():
    """Main dashboard with enhanced analytics"""
    user_id = g.user['id']
    smtp = account_store.get_config(user_id, 'smtp_servers', {'smtp_servers': []}).get('smtp_servers', [])
    lists = account_store.get_config(user_id, 'email_lists', {'email_lists': {'default': []}}).get('email_lists', {})
    templates = account_store.get_config(user_id, 'templates', {'email_templates': {'default': {}}}).get('email_templates', {})
    campaigns_cfg = account_store.get_config(user_id, 'campaigns', {'campaigns': {}}).get('campaigns', {})
    system_status = {
        'smtp_configured': any(s.get('enabled') for s in smtp),
        'total_smtp_servers': len(smtp),
        'total_recipients': sum(len(v) for v in lists.values()),
        'total_templates': len(templates),
        'total_campaigns': len(campaigns_cfg),
    }
    # Load recent analytics
    analytics_file = user_analytics_file(user_id)
    recent_campaigns = []
    if analytics_file.exists():
        with open(analytics_file, 'r') as f:
            all_campaigns = json.load(f)
            recent_campaigns = all_campaigns[-5:]  # Last 5 campaigns
    
    system_status['recent_campaigns'] = recent_campaigns
    return render_template('index.html', system_status=system_status)

@app.route('/healthz', methods=['GET'])
def healthz():
    """Unauthenticated health endpoint for the hosting platform."""
    return {"status": "ok"}, 200

@app.route('/api/test-smtp', methods=['POST'])
@login_required
def test_smtp():
    """Test SMTP connection with rotation support"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"})

        # Test single server or multiple servers
        if isinstance(data, list):
            # Multiple servers
            results = []
            for server_config in data:
                try:
                    if server_config.get('use_ssl', False) or server_config.get('port') == 465:
                        server = smtplib.SMTP_SSL(server_config['host'], server_config['port'], timeout=20)
                    else:
                        server = smtplib.SMTP(server_config['host'], server_config['port'], timeout=20)
                        if server_config.get('use_tls', True):
                            server.starttls()
                    server.login(server_config['username'], server_config['password'])
                    server.quit()
                    results.append({"server": server_config['name'], "status": "success"})
                except Exception as e:
                    results.append({"server": server_config['name'], "status": "failed", "error": str(e)})
            
            return jsonify({"success": True, "results": results})
        else:
            # Single server
            if data.get('use_ssl', False) or data.get('port') == 465:
                server = smtplib.SMTP_SSL(data['host'], data['port'], timeout=20)
            else:
                server = smtplib.SMTP(data['host'], data['port'], timeout=20)
                if data.get('use_tls', True):
                    server.starttls()
            server.login(data['username'], data['password'])
            server.quit()
            return jsonify({"success": True, "message": "SMTP connection successful!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"SMTP connection failed: {str(e)}"})

@app.route('/api/validate-emails', methods=['POST'])
@login_required
def validate_emails():
    """Validate email addresses with enhanced feedback"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"})

        emails = data.get('emails', [])
        valid_emails = []
        invalid_emails = []

        for email in emails:
            email = email.strip().lower()
            if validate_email_address(email):
                if email not in [e['email'] for e in valid_emails]:  # Deduplicate
                    valid_emails.append({
                        "email": email,
                        "status": "valid",
                        "domain": email.split('@')[1] if '@' in email else ""
                    })
            else:
                invalid_emails.append({
                    "email": email,
                    "status": "invalid",
                    "reason": "Invalid format"
                })

        return jsonify({
            "success": True,
            "valid_emails": valid_emails,
            "invalid_emails": invalid_emails,
            "total_valid": len(valid_emails),
            "total_invalid": len(invalid_emails),
            "duplicate_count": len(emails) - len(valid_emails) - len(invalid_emails)
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/send-emails', methods=['POST'])
@login_required
def send_emails():
    """Send emails with SMTP rotation and real-time progress"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"})

        # Validate required data
        smtp_configs = account_store.get_config(g.user['id'], 'smtp_servers', {'smtp_servers': []}).get('smtp_servers', [])
        content = data.get('content')
        stored_lists = account_store.get_config(g.user['id'], 'email_lists', {'email_lists': {'default': []}}).get('email_lists', {})
        recipients = [recipient for group in stored_lists.values() for recipient in group]
        attachments = data.get('attachments', [])
        dry_run = data.get('dry_run', True)
        
        # Rotation settings
        rotation_mode = data.get('rotation_mode', 'email_count')
        rotation_value = data.get('rotation_value', 10)
        try:
            delay_between_emails = max(1.0, min(float(data.get('delay_between_emails', 1)), 60.0))
        except (TypeError, ValueError):
            delay_between_emails = 1.0
        batch_size = data.get('batch_size', 50)
        max_retries = data.get('max_retries', 3)

        # Detailed validation
        if data.get('consent_confirmed') is not True:
            return jsonify({"success": False, "message": "Confirm that every recipient agreed to receive this message."}), 400
        if not recipients or len(recipients) > 50:
            return jsonify({"success": False, "message": "Choose 1 to 50 saved, consented recipients for a personal send."}), 400
        if not all(isinstance(r, dict) and validate_email_address(str(r.get('email', ''))) for r in recipients):
            return jsonify({"success": False, "message": "Saved recipient list contains an invalid email address."}), 400
        if not smtp_configs:
            return jsonify({"success": False, "message": "No SMTP servers configured"})
        
        if not content or not content.get('subject') or not content.get('body'):
            return jsonify({"success": False, "message": "Email content is incomplete"})
        
        if not recipients:
            return jsonify({"success": False, "message": "No recipients provided"})

        # Filter enabled SMTP servers and let the configured rotation strategy
        # select among all of this user's accounts.
        # Each account belongs to the signed-in user. Pass all enabled accounts
        # to the existing rotation manager so users can use any number of their
        # own SMTP providers/accounts; do not silently restrict sends to one.
        enabled_configs = [config for config in smtp_configs if config.get('enabled', True)]
        if not enabled_configs:
            return jsonify({"success": False, "message": "No enabled SMTP servers found"})

        # Create sender with rotation
        sender = WebEmailSender(enabled_configs, rotation_mode, rotation_value, analytics_file=user_analytics_file(g.user['id']))

        # Prepare attachment paths
        attachment_paths = []
        for attachment in attachments:
            stored_name = secure_filename(str(attachment.get('stored_name', '')))
            if not stored_name or stored_name != attachment.get('stored_name'):
                continue
            try:
                attachment_id = str(uuid.UUID(str(attachment.get('id', ''))))
            except ValueError:
                continue
            if not stored_name.startswith(attachment_id + '_'):
                continue
            file_path = (user_upload_folder(g.user['id']) / stored_name).resolve()
            if file_path.parent == user_upload_folder(g.user['id']).resolve() and file_path.is_file():
                attachment_paths.append({
                    'id': attachment_id,
                    'inline': bool(attachment.get('inline')),
                    'path': str(file_path),
                })

        job_id = str(uuid.uuid4())
        with SEND_JOBS_LOCK:
            if len(SEND_JOBS) >= 50:
                for old_id in list(SEND_JOBS):
                    if SEND_JOBS[old_id]['status'] in ('complete', 'failed'):
                        SEND_JOBS.pop(old_id, None)
                    if len(SEND_JOBS) < 40:
                        break
            SEND_JOBS[job_id] = {"status": "running", "results": None, "error": None, "user_id": g.user['id']}
        threading.Thread(
            target=_run_send_job,
            args=(job_id, sender, content, [r['email'] for r in recipients], attachment_paths, dry_run, delay_between_emails),
            daemon=True,
            name=f"send-{job_id[:8]}",
        ).start()
        return jsonify({"success": True, "job_id": job_id, "message": "Campaign started"}), 202

    except Exception as e:
        import traceback
        print(f"Send emails error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"success": False, "message": f"Server error: {str(e)}"})


@app.route('/api/send-status/<job_id>', methods=['GET'])
@login_required
def send_status(job_id):
    try:
        safe_id = str(uuid.UUID(job_id))
    except (ValueError, TypeError, AttributeError):
        return jsonify({"success": False, "message": "Invalid job ID"}), 400
    with SEND_JOBS_LOCK:
        job = SEND_JOBS.get(safe_id)
        if not job or job.get('user_id') != g.user['id']:
            return jsonify({"success": False, "message": "Campaign job not found"}), 404
        return jsonify({"success": True, **copy.deepcopy(job)})

@app.route('/api/analytics', methods=['GET'])
@login_required
def get_analytics():
    """Get comprehensive analytics data"""
    try:
        analytics_file = user_analytics_file(g.user['id'])
        
        if not analytics_file.exists():
            return jsonify({
                "success": True,
                "data": {
                    "total_campaigns": 0,
                    "total_emails_sent": 0,
                    "total_emails_failed": 0,
                    "average_success_rate": 0,
                    "recent_campaigns": [],
                    "smtp_usage_summary": {}
                }
            })
        
        with open(analytics_file, 'r') as f:
            campaigns = json.load(f)
        
        # Calculate summary statistics
        total_campaigns = len(campaigns)
        total_emails_sent = sum(c.get('emails_sent', 0) for c in campaigns)
        total_emails_failed = sum(c.get('emails_failed', 0) for c in campaigns)
        
        success_rates = [c.get('success_rate', 0) for c in campaigns if c.get('success_rate') is not None]
        average_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0
        
        # SMTP usage summary
        smtp_usage_summary = {}
        for campaign in campaigns:
            smtp_usage = campaign.get('smtp_usage', {})
            for smtp_name, count in smtp_usage.items():
                if smtp_name not in smtp_usage_summary:
                    smtp_usage_summary[smtp_name] = 0
                smtp_usage_summary[smtp_name] += count
        
        return jsonify({
            "success": True,
            "data": {
                "total_campaigns": total_campaigns,
                "total_emails_sent": total_emails_sent,
                "total_emails_failed": total_emails_failed,
                "average_success_rate": round(average_success_rate, 2),
                "recent_campaigns": campaigns[-10:],  # Last 10 campaigns
                "smtp_usage_summary": smtp_usage_summary
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/config/smtp-servers', methods=['GET'])
@login_required
def get_smtp_servers():
    """Get configured SMTP servers"""
    try:
        smtp_servers = account_store.get_config(g.user['id'], 'smtp_servers', {'smtp_servers': []}).get('smtp_servers', [])
        return jsonify({
            "success": True,
            "smtp_servers": smtp_servers
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/config/smtp-servers', methods=['POST'])
@login_required
def save_smtp_servers():
    """Save SMTP servers configuration"""
    try:
        data = request.get_json()
        if not data or 'smtp_servers' not in data:
            return jsonify({"success": False, "message": "No SMTP servers data provided"})
        
        # Update the configuration file
        if not isinstance(data.get('smtp_servers'), list):
            return jsonify({"success": False, "message": "SMTP server list must be an array"}), 400
        account_store.save_config(g.user['id'], 'smtp_servers', data, secret=True)
        
        return jsonify({
            "success": True,
            "message": "SMTP servers saved successfully"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/config/email-lists', methods=['GET'])
@login_required
def get_email_lists():
    """Get available email lists"""
    try:
        email_lists = account_store.get_config(g.user['id'], 'email_lists', {'email_lists': {'default': []}}).get('email_lists', {})
        return jsonify({
            "success": True,
            "email_lists": email_lists
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/config/email-lists', methods=['POST'])
@login_required
def save_email_lists():
    """Save email lists configuration"""
    try:
        data = request.get_json()
        if not data or 'email_lists' not in data:
            return jsonify({"success": False, "message": "No email lists data provided"})
        
        # Update the configuration file
        account_store.save_config(g.user['id'], 'email_lists', data)
        
        return jsonify({
            "success": True,
            "message": "Email lists saved successfully"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/config/templates', methods=['GET'])
@login_required
def get_templates():
    """Get email templates"""
    try:
        templates = account_store.get_config(g.user['id'], 'templates', {'email_templates': {'default': {}}}).get('email_templates', {})
        return jsonify({
            "success": True,
            "templates": templates
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/config/templates', methods=['POST'])
@login_required
def save_templates():
    """Save email templates configuration"""
    try:
        data = request.get_json()
        if not data or 'email_templates' not in data:
            return jsonify({"success": False, "message": "No templates data provided"})
        
        # Update the configuration file
        account_store.save_config(g.user['id'], 'templates', data)
        
        return jsonify({
            "success": True,
            "message": "Email templates saved successfully"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/upload-csv', methods=['POST'])
@login_required
def upload_csv():
    """Upload and process CSV file with enhanced validation"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No file uploaded"})

        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"})

        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = user_upload_folder(g.user['id']) / filename
            file.save(filepath)

            # Process CSV with enhanced validation
            with open(filepath, 'r', newline='', encoding='utf-8-sig') as csv_file:
                reader = csv.DictReader(csv_file)
                columns = reader.fieldnames or []
                rows = list(reader)

            # Find email columns
            email_columns = [col for col in columns if 'email' in col.lower()]
            if not email_columns:
                return jsonify({"success": False, "message": "No email column found in CSV"})

            email_col = email_columns[0]
            raw_emails = [row.get(email_col, '') for row in rows if row.get(email_col, '').strip()]

            # Enhanced processing with domain analysis
            processed_data = []
            domains = {}
            
            for row in rows:
                email = str(row.get(email_col, '')).strip().lower()
                if validate_email_address(email):
                    row_data = {"email": email}
                    # Add other columns as additional data
                    for col in columns:
                        if col != email_col:
                            row_data[col] = str(row.get(col) or "").strip()
                    
                    # Track domains
                    domain = email.split('@')[1] if '@' in email else 'unknown'
                    domains[domain] = domains.get(domain, 0) + 1
                    
                    processed_data.append(row_data)

            # Clean up file
            os.remove(filepath)

            return jsonify({
                "success": True,
                "message": f"Successfully processed {len(processed_data)} valid emails",
                "emails": processed_data,
                "total_processed": len(raw_emails),
                "total_valid": len(processed_data),
                "domain_breakdown": domains,
                "columns_found": list(columns)
            })

        return jsonify({"success": False, "message": "Invalid file type"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/upload-attachment', methods=['POST'])
@login_required
def upload_attachment():
    """Upload attachment files"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No file uploaded"})

        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"})

        if file and file.filename and allowed_file(file.filename):
            # Generate unique filename
            file_id = str(uuid.uuid4())
            filename = secure_filename(file.filename)
            new_filename = f"{file_id}_{filename}"
            filepath = user_upload_folder(g.user['id']) / new_filename
            file.save(filepath)

            file_info = {
                "id": file_id,
                "original_name": filename,
                "stored_name": new_filename,
                "size": os.path.getsize(filepath)
            }

            return jsonify({
                "success": True,
                "message": "File uploaded successfully",
                "file": file_info
            })

        return jsonify({"success": False, "message": "Invalid file type"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/cleanup-files', methods=['POST'])
@login_required
def cleanup_files():
    """Clean up uploaded files"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"})

        file_ids = data.get('file_ids', [])

        for file_id in file_ids:
            # Only accept an upload ID, never a user-controlled glob pattern.
            try:
                safe_id = str(uuid.UUID(str(file_id)))
            except (ValueError, TypeError, AttributeError):
                continue
            for file_path in user_upload_folder(g.user['id']).glob(f"{safe_id}_*"):
                if file_path.exists():
                    os.remove(file_path)

        return jsonify({"success": True, "message": "Files cleaned up"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/config/campaigns', methods=['GET'])
@login_required
def get_campaigns():
    """Get campaign configurations"""
    try:
        campaigns = account_store.get_config(g.user['id'], 'campaigns', {'campaigns': {}}).get('campaigns', {})
        return jsonify({
            "success": True,
            "campaigns": campaigns
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/config/campaigns', methods=['POST'])
@login_required
def save_campaigns():
    """Save campaign configurations"""
    try:
        data = request.get_json()
        if not data or 'campaigns' not in data:
            return jsonify({"success": False, "message": "No campaigns data provided"})
        
        # Load existing config and update campaigns
        account_store.save_config(g.user['id'], 'campaigns', {'campaigns': data['campaigns']})
        
        return jsonify({
            "success": True,
            "message": "Campaigns saved successfully"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    # Keep the personal desktop app private unless deployed deliberately.
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')), debug=False)
