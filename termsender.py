
#!/usr/bin/env python3
"""
TermSender Pro - Enhanced CLI with SMTP Rotation & Advanced Analytics
Advanced terminal email sender with sophisticated campaign management
"""

import smtplib
import os
import json
import csv
import time
import threading
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import random

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.progress import Progress, TaskID, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich import box
from email_validator import validate_email, EmailNotValidError

# Initialize Typer app and Rich console
app = typer.Typer(
    name="TermSender Pro",
    help="Professional terminal email sender with SMTP rotation and advanced analytics",
    rich_markup_mode="rich"
)
console = Console()

# Configuration directories
CONFIG_DIR = Path("config")
LOGS_DIR = Path("logs")
ANALYTICS_DIR = Path("analytics")

# Create directories
for directory in [CONFIG_DIR, LOGS_DIR, ANALYTICS_DIR]:
    directory.mkdir(exist_ok=True)

@dataclass
class SMTPServer:
    """SMTP Server configuration"""
    name: str
    host: str
    port: int
    username: str
    password: str
    sender_email: str
    use_tls: bool = True
    use_ssl: bool = False
    enabled: bool = True
    max_emails_per_hour: int = 300
    current_emails_sent: int = 0
    last_reset_time: datetime = None
    connection_status: str = "unknown"
    
    def __post_init__(self):
        if self.last_reset_time is None:
            self.last_reset_time = datetime.now()

@dataclass
class CampaignStats:
    """Campaign statistics tracking"""
    campaign_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_recipients: int = 0
    emails_sent: int = 0
    emails_failed: int = 0
    smtp_rotations: int = 0
    current_smtp: str = ""
    failed_recipients: List[Dict] = None
    smtp_usage: Dict[str, int] = None
    
    def __post_init__(self):
        if self.failed_recipients is None:
            self.failed_recipients = []
        if self.smtp_usage is None:
            self.smtp_usage = {}

class SMTPRotationManager:
    """Advanced SMTP rotation and management"""
    
    def __init__(self, smtp_servers: List[SMTPServer], rotation_mode: str = "email_count", rotation_value: int = 10):
        self.smtp_servers = [server for server in smtp_servers if server.enabled]
        self.rotation_mode = rotation_mode  # "email_count" or "time_based"
        self.rotation_value = rotation_value  # emails per rotation or seconds per rotation
        self.current_server_index = 0
        self.emails_sent_current_server = 0
        self.server_start_time = datetime.now()
        self.server_connections = {}
        
    def get_current_server(self) -> SMTPServer:
        """Get the currently active SMTP server"""
        if not self.smtp_servers:
            raise Exception("No enabled SMTP servers available")
        return self.smtp_servers[self.current_server_index]
    
    def should_rotate(self) -> bool:
        """Check if it's time to rotate to next SMTP server"""
        if len(self.smtp_servers) <= 1:
            return False
            
        if self.rotation_mode == "email_count":
            return self.emails_sent_current_server >= self.rotation_value
        elif self.rotation_mode == "time_based":
            elapsed = (datetime.now() - self.server_start_time).total_seconds()
            return elapsed >= self.rotation_value
        return False
    
    def rotate_server(self) -> SMTPServer:
        """Rotate to the next SMTP server"""
        self.current_server_index = (self.current_server_index + 1) % len(self.smtp_servers)
        self.emails_sent_current_server = 0
        self.server_start_time = datetime.now()
        
        # Close current connection if exists
        current_server = self.get_current_server()
        if current_server.name in self.server_connections:
            try:
                self.server_connections[current_server.name].quit()
            except:
                pass
            del self.server_connections[current_server.name]
        
        return current_server
    
    def get_server_connection(self, server: SMTPServer):
        """Get or create SMTP connection for server"""
        if server.name not in self.server_connections:
            try:
                # Prefer implicit SSL when configured (e.g., port 465)
                if server.use_ssl or server.port == 465:
                    connection = smtplib.SMTP_SSL(server.host, server.port, timeout=20)
                else:
                    connection = smtplib.SMTP(server.host, server.port, timeout=20)
                    if server.use_tls:
                        connection.starttls()
                connection.login(server.username, server.password)
                self.server_connections[server.name] = connection
                server.connection_status = "connected"
            except Exception as e:
                # Fallback: try the alternate mode and common alternate port
                try:
                    if server.use_ssl or server.port == 465:
                        # Try STARTTLS on port 587
                        fallback_port = 587
                        connection = smtplib.SMTP(server.host, fallback_port, timeout=20)
                        connection.starttls()
                    else:
                        # Try implicit SSL on port 465
                        fallback_port = 465
                        connection = smtplib.SMTP_SSL(server.host, fallback_port, timeout=20)
                    connection.login(server.username, server.password)
                    self.server_connections[server.name] = connection
                    server.connection_status = f"connected (fallback:{fallback_port})"
                except Exception:
                    server.connection_status = f"failed: {str(e)}"
                    raise e
        
        return self.server_connections[server.name]
    
    def record_email_sent(self):
        """Record that an email was sent"""
        self.emails_sent_current_server += 1
        current_server = self.get_current_server()
        current_server.current_emails_sent += 1
    
    def cleanup_connections(self):
        """Clean up all SMTP connections"""
        for connection in self.server_connections.values():
            try:
                connection.quit()
            except:
                pass
        self.server_connections.clear()

class AnalyticsManager:
    """Advanced analytics and reporting"""
    
    def __init__(self):
        self.analytics_file = ANALYTICS_DIR / "campaign_analytics.json"
        self.current_stats: Optional[CampaignStats] = None
    
    def start_campaign(self, campaign_id: str, total_recipients: int) -> CampaignStats:
        """Start tracking a new campaign"""
        self.current_stats = CampaignStats(
            campaign_id=campaign_id,
            start_time=datetime.now(),
            total_recipients=total_recipients
        )
        return self.current_stats
    
    def record_email_sent(self, smtp_server_name: str):
        """Record successful email send"""
        if self.current_stats:
            self.current_stats.emails_sent += 1
            self.current_stats.current_smtp = smtp_server_name
            if smtp_server_name not in self.current_stats.smtp_usage:
                self.current_stats.smtp_usage[smtp_server_name] = 0
            self.current_stats.smtp_usage[smtp_server_name] += 1
    
    def record_email_failed(self, recipient: str, error: str, smtp_server_name: str):
        """Record failed email send"""
        if self.current_stats:
            self.current_stats.emails_failed += 1
            self.current_stats.failed_recipients.append({
                "email": recipient,
                "error": error,
                "smtp_server": smtp_server_name,
                "timestamp": datetime.now().isoformat()
            })
    
    def record_smtp_rotation(self):
        """Record SMTP server rotation"""
        if self.current_stats:
            self.current_stats.smtp_rotations += 1
    
    def end_campaign(self):
        """End campaign tracking and save analytics"""
        if self.current_stats:
            self.current_stats.end_time = datetime.now()
            self._save_analytics()
    
    def _save_analytics(self):
        """Save analytics to file"""
        analytics_data = []
        
        if self.analytics_file.exists():
            with open(self.analytics_file, 'r') as f:
                analytics_data = json.load(f)
        
        # Convert stats to dict
        stats_dict = {
            "campaign_id": self.current_stats.campaign_id,
            "start_time": self.current_stats.start_time.isoformat(),
            "end_time": self.current_stats.end_time.isoformat() if self.current_stats.end_time else None,
            "total_recipients": self.current_stats.total_recipients,
            "emails_sent": self.current_stats.emails_sent,
            "emails_failed": self.current_stats.emails_failed,
            "smtp_rotations": self.current_stats.smtp_rotations,
            "failed_recipients": self.current_stats.failed_recipients,
            "smtp_usage": self.current_stats.smtp_usage,
            "success_rate": (self.current_stats.emails_sent / self.current_stats.total_recipients * 100) if self.current_stats.total_recipients > 0 else 0
        }
        
        analytics_data.append(stats_dict)
        
        with open(self.analytics_file, 'w') as f:
            json.dump(analytics_data, f, indent=2)

class ConfigurationManager:
    """Manage file-based configurations"""
    
    def __init__(self):
        self.smtp_config_file = CONFIG_DIR / "smtp_servers.json"
        self.email_lists_file = CONFIG_DIR / "email_lists.json"
        self.templates_file = CONFIG_DIR / "email_templates.json"
        self.campaigns_file = CONFIG_DIR / "campaign_settings.json"
    
    def load_smtp_servers(self) -> List[SMTPServer]:
        """Load SMTP servers from configuration file"""
        if not self.smtp_config_file.exists():
            return []
        
        with open(self.smtp_config_file, 'r') as f:
            data = json.load(f)
        
        servers = []
        for server_data in data.get('smtp_servers', []):
            server = SMTPServer(
                name=server_data['name'],
                host=server_data['host'],
                port=server_data['port'],
                username=server_data['username'],
                password=server_data['password'],
                sender_email=server_data['sender_email'],
                use_tls=server_data.get('use_tls', True),
                enabled=server_data.get('enabled', True),
                max_emails_per_hour=server_data.get('max_emails_per_hour', 300)
            )
            servers.append(server)
        
        return servers
    
    def load_email_list(self, list_name: str) -> List[Dict]:
        """Load email list from configuration file"""
        if not self.email_lists_file.exists():
            return []
        
        with open(self.email_lists_file, 'r') as f:
            data = json.load(f)
        
        return data.get('email_lists', {}).get(list_name, [])
    
    def load_email_template(self, template_name: str) -> Optional[Dict]:
        """Load email template from configuration file"""
        if not self.templates_file.exists():
            return None
        
        with open(self.templates_file, 'r') as f:
            data = json.load(f)
        
        return data.get('email_templates', {}).get(template_name)
    
    def load_campaign_config(self, campaign_name: str) -> Optional[Dict]:
        """Load campaign configuration from file"""
        if not self.campaigns_file.exists():
            return None
        
        with open(self.campaigns_file, 'r') as f:
            data = json.load(f)
        
        return data.get('campaigns', {}).get(campaign_name)
    
    def list_available_configs(self) -> Dict:
        """List all available configurations"""
        configs = {
            "smtp_servers": [],
            "email_lists": [],
            "templates": [],
            "campaigns": []
        }
        
        if self.smtp_config_file.exists():
            with open(self.smtp_config_file, 'r') as f:
                data = json.load(f)
                configs["smtp_servers"] = [s['name'] for s in data.get('smtp_servers', [])]
        
        if self.email_lists_file.exists():
            with open(self.email_lists_file, 'r') as f:
                data = json.load(f)
                configs["email_lists"] = list(data.get('email_lists', {}).keys())
        
        if self.templates_file.exists():
            with open(self.templates_file, 'r') as f:
                data = json.load(f)
                configs["templates"] = list(data.get('email_templates', {}).keys())
        
        if self.campaigns_file.exists():
            with open(self.campaigns_file, 'r') as f:
                data = json.load(f)
                configs["campaigns"] = list(data.get('campaigns', {}).keys())
        
        return configs

class AdvancedEmailSender:
    """Advanced email sender with SMTP rotation and analytics"""
    
    def __init__(self, smtp_servers: List[SMTPServer], rotation_mode: str = "email_count", rotation_value: int = 10):
        self.smtp_manager = SMTPRotationManager(smtp_servers, rotation_mode, rotation_value)
        self.analytics = AnalyticsManager()
        self.rate_limiter = RateLimiter()
        
    def send_campaign(self, recipients: List[Dict], email_content: Dict, attachments: List[str] = None, 
                     dry_run: bool = False, delay_between_emails: float = 1.0) -> CampaignStats:
        """Send email campaign with advanced features"""
        
        campaign_id = f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        stats = self.analytics.start_campaign(campaign_id, len(recipients))
        
        if dry_run:
            console.print(Panel(
                "[bold yellow]🧪 DRY RUN MODE - No emails will be sent[/bold yellow]",
                border_style="yellow"
            ))
        
        # Create progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("✅ Sent: [green]{task.fields[sent]}[/green]"),
            TextColumn("•"),
            TextColumn("❌ Failed: [red]{task.fields[failed]}[/red]"),
            TextColumn("•"),
            TextColumn("🔄 SMTP: [cyan]{task.fields[current_smtp]}[/cyan]"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task(
                "Sending emails...",
                total=len(recipients),
                sent=0,
                failed=0,
                current_smtp=self.smtp_manager.get_current_server().name
            )
            
            for i, recipient in enumerate(recipients):
                try:
                    # Check if we should rotate SMTP servers
                    if self.smtp_manager.should_rotate():
                        new_server = self.smtp_manager.rotate_server()
                        self.analytics.record_smtp_rotation()
                        progress.update(task, current_smtp=new_server.name)
                        console.print(f"🔄 [cyan]Rotated to SMTP: {new_server.name}[/cyan]")
                    
                    current_server = self.smtp_manager.get_current_server()
                    
                    if not dry_run:
                        # Get SMTP connection
                        server_connection = self.smtp_manager.get_server_connection(current_server)
                        
                        # Create email message
                        msg = self._create_email_message(recipient, email_content, current_server, attachments)
                        
                        # Send email
                        server_connection.sendmail(
                            current_server.sender_email,
                            recipient['email'],
                            msg.as_string()
                        )
                    
                    # Record success
                    self.smtp_manager.record_email_sent()
                    self.analytics.record_email_sent(current_server.name)
                    
                    progress.update(
                        task,
                        advance=1,
                        sent=stats.emails_sent,
                        failed=stats.emails_failed
                    )
                    
                    # Rate limiting
                    time.sleep(delay_between_emails)
                    
                except Exception as e:
                    # Record failure
                    self.analytics.record_email_failed(
                        recipient['email'], 
                        str(e), 
                        self.smtp_manager.get_current_server().name
                    )
                    
                    progress.update(
                        task,
                        advance=1,
                        sent=stats.emails_sent,
                        failed=stats.emails_failed
                    )
                    
                    console.print(f"❌ [red]Failed to send to {recipient['email']}: {str(e)}[/red]")
        
        # Cleanup
        self.smtp_manager.cleanup_connections()
        self.analytics.end_campaign()
        
        return stats
    
    def _create_email_message(self, recipient: Dict, content: Dict, server: SMTPServer, attachments: List[str] = None):
        """Create email message with content and attachments"""
        msg = MIMEMultipart()
        msg['From'] = server.sender_email
        msg['To'] = recipient['email']
        msg['Subject'] = self._render_template(content['subject'], recipient)
        
        # Add body
        body = self._render_template(content['body'], recipient)
        body_type = 'html' if content.get('is_html', False) else 'plain'
        msg.attach(MIMEText(body, body_type))
        
        # Add attachments
        if attachments:
            for attachment_path in attachments:
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
        
        return msg
    
    def _render_template(self, template: str, recipient: Dict) -> str:
        """Render template with recipient data"""
        rendered = template
        for key, value in recipient.items():
            placeholder = f"{{{key}}}"
            rendered = rendered.replace(placeholder, str(value))
        return rendered

class RateLimiter:
    """Advanced rate limiting functionality"""
    
    def __init__(self):
        self.email_timestamps = []
        self.max_emails_per_minute = 60
        self.max_emails_per_hour = 1000
    
    def can_send_email(self) -> bool:
        """Check if we can send another email based on rate limits"""
        now = datetime.now()
        
        # Clean old timestamps
        self.email_timestamps = [
            ts for ts in self.email_timestamps 
            if now - ts < timedelta(hours=1)
        ]
        
        # Check hourly limit
        if len(self.email_timestamps) >= self.max_emails_per_hour:
            return False
        
        # Check per-minute limit
        recent_emails = [
            ts for ts in self.email_timestamps 
            if now - ts < timedelta(minutes=1)
        ]
        
        if len(recent_emails) >= self.max_emails_per_minute:
            return False
        
        return True
    
    def record_email_sent(self):
        """Record that an email was sent"""
        self.email_timestamps.append(datetime.now())

def show_analytics_dashboard():
    """Display comprehensive analytics dashboard"""
    analytics_file = ANALYTICS_DIR / "campaign_analytics.json"
    
    if not analytics_file.exists():
        console.print("[yellow]No analytics data available yet.[/yellow]")
        return
    
    with open(analytics_file, 'r') as f:
        analytics_data = json.load(f)
    
    if not analytics_data:
        console.print("[yellow]No campaigns recorded yet.[/yellow]")
        return
    
    # Summary table
    summary_table = Table(title="📊 Campaign Analytics Summary", box=box.ROUNDED)
    summary_table.add_column("Campaign ID", style="cyan")
    summary_table.add_column("Date", style="white")
    summary_table.add_column("Recipients", style="blue")
    summary_table.add_column("Sent", style="green")
    summary_table.add_column("Failed", style="red")
    summary_table.add_column("Success Rate", style="yellow")
    summary_table.add_column("SMTP Rotations", style="magenta")
    
    total_sent = 0
    total_failed = 0
    total_rotations = 0
    
    for campaign in analytics_data[-10:]:  # Show last 10 campaigns
        start_time = datetime.fromisoformat(campaign['start_time'])
        success_rate = f"{campaign.get('success_rate', 0):.1f}%"
        
        summary_table.add_row(
            campaign['campaign_id'],
            start_time.strftime('%Y-%m-%d %H:%M'),
            str(campaign['total_recipients']),
            str(campaign['emails_sent']),
            str(campaign['emails_failed']),
            success_rate,
            str(campaign.get('smtp_rotations', 0))
        )
        
        total_sent += campaign['emails_sent']
        total_failed += campaign['emails_failed']
        total_rotations += campaign.get('smtp_rotations', 0)
    
    console.print(summary_table)
    
    # SMTP Usage Analysis
    if analytics_data:
        latest_campaign = analytics_data[-1]
        if 'smtp_usage' in latest_campaign and latest_campaign['smtp_usage']:
            smtp_table = Table(title="🔄 SMTP Server Usage (Latest Campaign)", box=box.ROUNDED)
            smtp_table.add_column("SMTP Server", style="cyan")
            smtp_table.add_column("Emails Sent", style="green")
            smtp_table.add_column("Percentage", style="yellow")
            
            total_emails = sum(latest_campaign['smtp_usage'].values())
            for smtp_name, count in latest_campaign['smtp_usage'].items():
                percentage = f"{(count/total_emails*100):.1f}%" if total_emails > 0 else "0%"
                smtp_table.add_row(smtp_name, str(count), percentage)
            
            console.print(smtp_table)
    
    # Overall Statistics
    overall_stats = Panel(
        f"[bold]Total Campaigns:[/bold] {len(analytics_data)}\n"
        f"[bold]Total Emails Sent:[/bold] [green]{total_sent}[/green]\n"
        f"[bold]Total Failures:[/bold] [red]{total_failed}[/red]\n"
        f"[bold]Total SMTP Rotations:[/bold] [magenta]{total_rotations}[/magenta]\n"
        f"[bold]Overall Success Rate:[/bold] [yellow]{(total_sent/(total_sent+total_failed)*100):.1f}%[/yellow]" if (total_sent + total_failed) > 0 else "[bold]Overall Success Rate:[/bold] [yellow]N/A[/yellow]",
        title="📈 Overall Statistics",
        border_style="green"
    )
    
    console.print(overall_stats)

@app.command()
def send(
    smtp_config: str = typer.Option(None, "--smtp-config", "-s", help="SMTP configuration name from config file"),
    email_list: str = typer.Option(None, "--email-list", "-l", help="Email list name from config file"),
    template: str = typer.Option(None, "--template", "-t", help="Email template name from config file"),
    rotation_mode: str = typer.Option("email_count", "--rotation-mode", "-r", help="SMTP rotation mode: email_count or time_based"),
    rotation_value: int = typer.Option(10, "--rotation-value", "-v", help="Emails per rotation or seconds per rotation"),
    delay: float = typer.Option(1.0, "--delay", "-d", help="Delay between emails in seconds"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Test mode - don't actually send emails"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Use interactive mode")
):
    """🚀 Send email campaigns with advanced SMTP rotation"""
    
    config_manager = ConfigurationManager()
    
    # Show welcome
    show_welcome()
    
    if interactive:
        # Interactive mode
        smtp_servers = configure_smtp_interactive(config_manager)
        recipients = load_recipients_interactive(config_manager)
        email_content = compose_email_interactive(config_manager)
    else:
        # File-based mode
        if not all([smtp_config, email_list, template]):
            console.print("[red]❌ For non-interactive mode, you must specify --smtp-config, --email-list, and --template[/red]")
            raise typer.Exit(1)
        
        smtp_servers = config_manager.load_smtp_servers()
        if smtp_config != "all":
            smtp_servers = [s for s in smtp_servers if s.name == smtp_config]
        
        recipients_data = config_manager.load_email_list(email_list)
        recipients = [{"email": r["email"], **r} for r in recipients_data]
        
        template_data = config_manager.load_email_template(template)
        if not template_data:
            console.print(f"[red]❌ Template '{template}' not found[/red]")
            raise typer.Exit(1)
        
        email_content = template_data
    
    if not smtp_servers:
        console.print("[red]❌ No SMTP servers configured[/red]")
        raise typer.Exit(1)
    
    if not recipients:
        console.print("[red]❌ No recipients loaded[/red]")
        raise typer.Exit(1)
    
    # Show configuration summary
    show_campaign_summary(smtp_servers, recipients, email_content, rotation_mode, rotation_value)
    
    if not dry_run and not Confirm.ask(f"[bold red]🚨 Send {len(recipients)} REAL emails?[/bold red]"):
        console.print("[yellow]Campaign cancelled[/yellow]")
        raise typer.Exit(0)
    
    # Send campaign
    sender = AdvancedEmailSender(smtp_servers, rotation_mode, rotation_value)
    stats = sender.send_campaign(recipients, email_content, dry_run=dry_run, delay_between_emails=delay)
    
    # Show results
    show_campaign_results(stats, dry_run)

@app.command()
def campaign(
    name: str = typer.Argument(..., help="Campaign name from configuration file"),
    dry_run: bool = typer.Option(True, "--dry-run/--live", help="Test mode or live sending")
):
    """🎯 Run a pre-configured campaign from file"""
    
    config_manager = ConfigurationManager()
    
    # Load campaign configuration
    campaign_config = config_manager.load_campaign_config(name)
    if not campaign_config:
        console.print(f"[red]❌ Campaign '{name}' not found[/red]")
        show_available_campaigns(config_manager)
        raise typer.Exit(1)
    
    console.print(f"[bold cyan]🎯 Running Campaign: {campaign_config.get('name', name)}[/bold cyan]")
    
    # Load components
    smtp_servers = config_manager.load_smtp_servers()
    smtp_server_name = campaign_config.get('smtp_server')
    if smtp_server_name and smtp_server_name != "all":
        smtp_servers = [s for s in smtp_servers if s.name == smtp_server_name]
    
    email_list_name = campaign_config.get('email_list')
    recipients_data = config_manager.load_email_list(email_list_name)
    recipients = [{"email": r["email"], **r} for r in recipients_data]
    
    template_name = campaign_config.get('template')
    email_content = config_manager.load_email_template(template_name)
    
    # Get campaign settings
    settings = campaign_config.get('settings', {})
    rotation_mode = settings.get('rotation_mode', 'email_count')
    rotation_value = settings.get('rotation_value', 10)
    delay = settings.get('delay_between_emails', 1.0)
    
    # Override dry_run if specified in campaign
    if 'send_mode' in settings:
        dry_run = settings['send_mode'] == 'dry_run'
    
    # Show summary and run
    show_campaign_summary(smtp_servers, recipients, email_content, rotation_mode, rotation_value)
    
    sender = AdvancedEmailSender(smtp_servers, rotation_mode, rotation_value)
    stats = sender.send_campaign(recipients, email_content, dry_run=dry_run, delay_between_emails=delay)
    
    show_campaign_results(stats, dry_run)

@app.command()
def analytics():
    """📊 View detailed campaign analytics"""
    show_analytics_dashboard()

@app.command()
def config():
    """⚙️ Show configuration overview"""
    config_manager = ConfigurationManager()
    configs = config_manager.list_available_configs()
    
    console.print(Panel(
        f"[bold cyan]📁 Configuration Overview[/bold cyan]\n\n"
        f"[yellow]📧 SMTP Servers:[/yellow] {len(configs['smtp_servers'])}\n"
        f"[yellow]👥 Email Lists:[/yellow] {len(configs['email_lists'])}\n" 
        f"[yellow]📝 Templates:[/yellow] {len(configs['templates'])}\n"
        f"[yellow]🎯 Campaigns:[/yellow] {len(configs['campaigns'])}\n\n"
        f"[dim]Config files location: {CONFIG_DIR}[/dim]",
        title="Configuration Status",
        border_style="blue"
    ))
    
    # Show details
    for config_type, items in configs.items():
        if items:
            console.print(f"\n[bold]{config_type.replace('_', ' ').title()}:[/bold]")
            for item in items:
                console.print(f"  • {item}")

def show_welcome():
    """Enhanced welcome screen"""
    welcome_art = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║    ████████╗███████╗██████╗ ███╗   ███╗███████╗███████╗    ║
    ║    ╚══██╔══╝██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝    ║
    ║       ██║   █████╗  ██████╔╝██╔████╔██║███████╗█████╗      ║
    ║       ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║╚════██║██╔══╝      ║
    ║       ██║   ███████╗██║  ██║██║ ╚═╝ ██║███████║███████╗    ║
    ║       ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝    ║
    ║                                                              ║
    ║            Professional Email Campaign Manager               ║
    ║                    Advanced CLI v3.0                        ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    
    console.print(welcome_art, style="bold cyan")
    
    features = [
        "🔄 Advanced SMTP rotation (email count / time-based)",
        "📊 Real-time analytics and success tracking",
        "📁 File-based configuration support",
        "🎯 Pre-configured campaign management",
        "⚡ Rate limiting and delivery optimization",
        "🛡️ Enhanced error handling and retry logic"
    ]
    
    console.print("\n[bold green]🚀 Advanced Features:[/bold green]")
    for feature in features:
        console.print(f"  {feature}")
    
    console.print("\n" + "="*60)

def configure_smtp_interactive(config_manager: ConfigurationManager) -> List[SMTPServer]:
    """Interactive SMTP configuration"""
    console.print(Panel(
        "[bold cyan]📧 SMTP Configuration[/bold cyan]\n"
        "Configure multiple SMTP servers for rotation",
        title="SMTP Setup",
        border_style="blue"
    ))
    
    # Check for existing configuration
    existing_servers = config_manager.load_smtp_servers()
    if existing_servers:
        console.print(f"[green]✅ Found {len(existing_servers)} configured SMTP servers[/green]")
        for server in existing_servers:
            status = "🟢" if server.enabled else "🔴"
            console.print(f"  {status} {server.name} ({server.host})")
        
        if Confirm.ask("Use existing SMTP configuration?", default=True):
            return [s for s in existing_servers if s.enabled]
    
    # Configure new servers
    servers = []
    while True:
        console.print(f"\n[bold]Configuring SMTP Server #{len(servers) + 1}[/bold]")
        
        name = Prompt.ask("Server name", default=f"SMTP-{len(servers) + 1}")
        host = Prompt.ask("SMTP Host", default="smtp.gmail.com")
        port = IntPrompt.ask("SMTP Port", default=587)
        username = Prompt.ask("Username/Email")
        password = Prompt.ask("Password", password=True)
        sender_email = Prompt.ask("Sender Email", default=username)
        use_tls = Confirm.ask("Use TLS?", default=True)
        
        server = SMTPServer(name, host, port, username, password, sender_email, use_tls)
        
        # Test connection
        if test_smtp_connection(server):
            servers.append(server)
            console.print(f"[green]✅ {name} added successfully[/green]")
        else:
            console.print(f"[red]❌ Failed to add {name}[/red]")
        
        if not Confirm.ask("Add another SMTP server?", default=False):
            break
    
    return servers

def load_recipients_interactive(config_manager: ConfigurationManager) -> List[Dict]:
    """Interactive recipient loading"""
    console.print(Panel(
        "[bold cyan]👥 Recipient Management[/bold cyan]\n"
        "Load recipients from files or enter manually",
        title="Recipients",
        border_style="green"
    ))
    
    method = Prompt.ask(
        "Load method",
        choices=["file", "csv", "manual"],
        default="file"
    )
    
    if method == "file":
        # Show available email lists
        configs = config_manager.list_available_configs()
        if configs['email_lists']:
            console.print("Available email lists:")
            for list_name in configs['email_lists']:
                console.print(f"  • {list_name}")
            
            list_name = Prompt.ask("Email list name")
            recipients_data = config_manager.load_email_list(list_name)
            return [{"email": r["email"], **r} for r in recipients_data]
        else:
            console.print("[yellow]No email lists found in configuration[/yellow]")
            return load_recipients_csv()
    
    elif method == "csv":
        return load_recipients_csv()
    
    else:
        return load_recipients_manual()

def load_recipients_csv() -> List[Dict]:
    """Load recipients from CSV file"""
    file_path = Prompt.ask("CSV file path")
    
    if not os.path.exists(file_path):
        console.print(f"[red]❌ File not found: {file_path}[/red]")
        return []
    
    try:
        with open(file_path, 'r', newline='', encoding='utf-8-sig') as csv_file:
            reader = csv.DictReader(csv_file)
            columns = reader.fieldnames or []
            rows = list(reader)
        recipients = []
        
        # Find email column
        email_columns = [col for col in columns if 'email' in col.lower()]
        if not email_columns:
            console.print("[red]❌ No email column found[/red]")
            return []
        
        email_col = email_columns[0]
        
        for row in rows:
            email = str(row.get(email_col, '')).strip().lower()
            if validate_email_address(email):
                recipient = {"email": email}
                # Add other columns as additional data
                for col in columns:
                    if col != email_col:
                        recipient[col] = str(row.get(col) or "").strip()
                recipients.append(recipient)
        
        console.print(f"[green]✅ Loaded {len(recipients)} valid recipients[/green]")
        return recipients
        
    except Exception as e:
        console.print(f"[red]❌ Error loading CSV: {e}[/red]")
        return []

def load_recipients_manual() -> List[Dict]:
    """Manual recipient entry"""
    console.print("Enter email addresses (one per line, empty line to finish):")
    
    emails = []
    while True:
        email = input().strip()
        if not email:
            break
        
        if validate_email_address(email):
            emails.append({"email": email.lower()})
        else:
            console.print(f"[yellow]⚠️  Invalid email: {email}[/yellow]")
    
    return emails

def compose_email_interactive(config_manager: ConfigurationManager) -> Dict:
    """Interactive email composition"""
    console.print(Panel(
        "[bold cyan]✍️ Email Composition[/bold cyan]\n"
        "Create your email content",
        title="Compose",
        border_style="yellow"
    ))
    
    # Check for existing templates
    configs = config_manager.list_available_configs()
    if configs['templates']:
        console.print("Available templates:")
        for template_name in configs['templates']:
            console.print(f"  • {template_name}")
        
        if Confirm.ask("Use an existing template?", default=False):
            template_name = Prompt.ask("Template name")
            template_data = config_manager.load_email_template(template_name)
            if template_data:
                return template_data
    
    # Compose new email
    subject = Prompt.ask("Email subject")
    is_html = Confirm.ask("Use HTML format?", default=False)
    
    console.print("Enter email body (press Enter twice to finish):")
    lines = []
    empty_count = 0
    
    while empty_count < 2:
        line = input()
        if line == "":
            empty_count += 1
        else:
            empty_count = 0
        lines.append(line)
    
    # Remove trailing empty lines
    while lines and lines[-1] == "":
        lines.pop()
    
    body = "\n".join(lines)
    
    return {
        "subject": subject,
        "body": body,
        "is_html": is_html
    }

def test_smtp_connection(server: SMTPServer) -> bool:
    """Test SMTP connection"""
    try:
        with console.status(f"[yellow]Testing {server.name}...", spinner="dots"):
            if server.use_ssl or server.port == 465:
                connection = smtplib.SMTP_SSL(server.host, server.port)
            else:
                connection = smtplib.SMTP(server.host, server.port)
                if server.use_tls:
                    connection.starttls()
            connection.login(server.username, server.password)
            connection.quit()
        
        console.print(f"[green]✅ {server.name} connection successful[/green]")
        return True
    except Exception as e:
        console.print(f"[red]❌ {server.name} connection failed: {e}[/red]")
        return False

def validate_email_address(email: str) -> bool:
    """Validate email address"""
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False

def show_campaign_summary(smtp_servers: List[SMTPServer], recipients: List[Dict], 
                         email_content: Dict, rotation_mode: str, rotation_value: int):
    """Show campaign summary before sending"""
    summary_table = Table(title="📋 Campaign Summary", box=box.ROUNDED)
    summary_table.add_column("Component", style="bold cyan")
    summary_table.add_column("Details", style="white")
    
    summary_table.add_row("📧 Subject", email_content.get('subject', 'No subject'))
    summary_table.add_row("📄 Format", "HTML" if email_content.get('is_html', False) else "Plain Text")
    summary_table.add_row("👥 Recipients", str(len(recipients)))
    summary_table.add_row("📮 SMTP Servers", str(len(smtp_servers)))
    summary_table.add_row("🔄 Rotation Mode", f"{rotation_mode} ({rotation_value})")
    
    console.print(Panel(summary_table, border_style="blue"))
    
    # Show SMTP servers
    smtp_table = Table(title="🔄 SMTP Server Configuration", box=box.ROUNDED)
    smtp_table.add_column("Name", style="cyan")
    smtp_table.add_column("Host", style="white")
    smtp_table.add_column("Status", style="green")
    
    for server in smtp_servers:
        smtp_table.add_row(server.name, f"{server.host}:{server.port}", "✅ Ready")
    
    console.print(smtp_table)

def show_campaign_results(stats: CampaignStats, dry_run: bool):
    """Show detailed campaign results"""
    if dry_run:
        console.print(Panel(
            f"[bold yellow]🧪 DRY RUN COMPLETED[/bold yellow]\n\n"
            f"✅ Would have sent: {stats.emails_sent} emails\n"
            f"🔄 SMTP rotations: {stats.smtp_rotations}\n"
            f"⏱️ Simulation completed successfully",
            title="Test Results",
            border_style="yellow"
        ))
        return
    
    # Calculate statistics
    duration = stats.end_time - stats.start_time if stats.end_time else timedelta(0)
    success_rate = (stats.emails_sent / stats.total_recipients * 100) if stats.total_recipients > 0 else 0
    
    # Main results
    results_table = Table(title="📊 Campaign Results", box=box.ROUNDED)
    results_table.add_column("Metric", style="bold")
    results_table.add_column("Value", style="cyan")
    
    results_table.add_row("✅ Emails Sent", f"[green]{stats.emails_sent}[/green]")
    results_table.add_row("❌ Failed", f"[red]{stats.emails_failed}[/red]")
    results_table.add_row("📊 Success Rate", f"{success_rate:.1f}%")
    results_table.add_row("🔄 SMTP Rotations", str(stats.smtp_rotations))
    results_table.add_row("⏱️ Duration", str(duration).split('.')[0])
    
    console.print(Panel(results_table, border_style="green"))
    
    # SMTP usage breakdown
    if stats.smtp_usage:
        smtp_usage_table = Table(title="🔄 SMTP Server Usage", box=box.ROUNDED)
        smtp_usage_table.add_column("Server", style="cyan")
        smtp_usage_table.add_column("Emails Sent", style="green")
        smtp_usage_table.add_column("Percentage", style="yellow")
        
        total_sent = sum(stats.smtp_usage.values())
        for server_name, count in stats.smtp_usage.items():
            percentage = f"{(count/total_sent*100):.1f}%" if total_sent > 0 else "0%"
            smtp_usage_table.add_row(server_name, str(count), percentage)
        
        console.print(smtp_usage_table)
    
    # Show failures if any
    if stats.failed_recipients:
        console.print(f"\n[red]❌ Failed Recipients ({len(stats.failed_recipients)}):[/red]")
        for failure in stats.failed_recipients[:5]:  # Show first 5
            console.print(f"  • {failure['email']}: {failure['error']}")
        if len(stats.failed_recipients) > 5:
            console.print(f"  ... and {len(stats.failed_recipients) - 5} more")

def show_available_campaigns(config_manager: ConfigurationManager):
    """Show available campaigns"""
    configs = config_manager.list_available_configs()
    if configs['campaigns']:
        console.print("\n[bold]Available campaigns:[/bold]")
        for campaign_name in configs['campaigns']:
            console.print(f"  • {campaign_name}")
        console.print("\n[dim]Use: termsender campaign <name>[/dim]")

@app.command()
def version():
    """📋 Show version information"""
    console.print(Panel(
        "[bold cyan]TermSender Pro v3.0[/bold cyan]\n"
        "Advanced Email Campaign Manager with SMTP Rotation\n\n"
        "[yellow]🚀 Enhanced Features:[/yellow]\n"
        "• Multiple SMTP server rotation\n"
        "• Real-time analytics and tracking\n"
        "• File-based configuration system\n"
        "• Advanced rate limiting\n"
        "• Comprehensive campaign management\n"
        "• Professional terminal interface",
        title="📋 Version Info",
        border_style="cyan"
    ))

if __name__ == "__main__":
    app()
