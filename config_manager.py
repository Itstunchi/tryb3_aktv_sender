#!/usr/bin/env python3
"""
Configuration Manager for TermSender Pro
Handles both UI and file-based configurations
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import csv

class ConfigManager:
    """Manages all configuration files and settings"""
    
    def __init__(self):
        self.config_dir = Path('config')
        self.config_dir.mkdir(exist_ok=True)
        
        # Configuration file paths
        self.smtp_file = self.config_dir / 'smtp_servers.json'
        self.lists_file = self.config_dir / 'email_lists.json'
        self.templates_file = self.config_dir / 'email_templates.json'
        self.campaigns_file = self.config_dir / 'campaign_settings.json'
        
        # Initialize empty configs if files don't exist
        self._initialize_configs()
    
    def _initialize_configs(self):
        """Initialize configuration files with default values if they don't exist"""
        if not self.smtp_file.exists():
            self._create_default_smtp_config()
        if not self.lists_file.exists():
            self._create_default_lists_config()
        if not self.templates_file.exists():
            self._create_default_templates_config()
        if not self.campaigns_file.exists():
            self._create_default_campaigns_config()
    
    def _create_default_smtp_config(self):
        """Create default SMTP configuration"""
        default_config = {
            "smtp_servers": [
                {
                    "name": "Gmail SMTP",
                    "host": "smtp.gmail.com",
                    "port": 587,
                    "username": "",
                    "password": "",
                    "sender_email": "",
                    "use_tls": True,
                    "enabled": False
                }
            ]
        }
        self._save_config(self.smtp_file, default_config)
    
    def _create_default_lists_config(self):
        """Create default email lists configuration"""
        default_config = {
            "email_lists": {
                "default": []
            }
        }
        self._save_config(self.lists_file, default_config)
    
    def _create_default_templates_config(self):
        """Create default email templates configuration"""
        default_config = {
            "email_templates": {
                "default": {
                    "subject": "Default Subject",
                    "body": "Default email body content",
                    "is_html": False,
                    "variables": []
                }
            }
        }
        self._save_config(self.templates_file, default_config)
    
    def _create_default_campaigns_config(self):
        """Create default campaign settings"""
        default_config = {
            "default_settings": {
                "send_mode": "dry_run",
                "delay_between_emails": 1,
                "batch_size": 50,
                "max_retries": 3,
                "enable_tracking": False,
                "auto_unsubscribe": True
            },
            "campaigns": {}
        }
        self._save_config(self.campaigns_file, default_config)
    
    def _load_config(self, file_path: Path) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading config from {file_path}: {e}")
            return {}
    
    def _save_config(self, file_path: Path, config: Dict):
        """Save configuration to JSON file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config to {file_path}: {e}")
    
    # SMTP Configuration Methods
    def get_smtp_servers(self) -> List[Dict]:
        """Get all SMTP server configurations"""
        config = self._load_config(self.smtp_file)
        return config.get('smtp_servers', [])
    
    def get_enabled_smtp_server(self) -> Optional[Dict]:
        """Get the first enabled SMTP server"""
        servers = self.get_smtp_servers()
        for server in servers:
            if server.get('enabled', False):
                return server
        return None
    
    def add_smtp_server(self, server_config: Dict):
        """Add a new SMTP server configuration"""
        config = self._load_config(self.smtp_file)
        config['smtp_servers'] = config.get('smtp_servers', [])
        config['smtp_servers'].append(server_config)
        self._save_config(self.smtp_file, config)
    
    def update_smtp_server(self, server_name: str, server_config: Dict):
        """Update an existing SMTP server configuration"""
        config = self._load_config(self.smtp_file)
        servers = config.get('smtp_servers', [])
        
        for i, server in enumerate(servers):
            if server.get('name') == server_name:
                servers[i] = server_config
                break
        
        self._save_config(self.smtp_file, config)
    
    def enable_smtp_server(self, server_name: str):
        """Enable a specific SMTP server and disable others"""
        config = self._load_config(self.smtp_file)
        servers = config.get('smtp_servers', [])
        
        for server in servers:
            server['enabled'] = (server.get('name') == server_name)
        
        self._save_config(self.smtp_file, config)
    
    # Email Lists Methods
    def get_email_lists(self) -> Dict[str, List[Dict]]:
        """Get all email lists"""
        config = self._load_config(self.lists_file)
        return config.get('email_lists', {})
    
    def get_email_list(self, list_name: str) -> List[Dict]:
        """Get a specific email list"""
        lists = self.get_email_lists()
        return lists.get(list_name, [])
    
    def add_email_list(self, list_name: str, emails: List[Dict]):
        """Add a new email list"""
        config = self._load_config(self.lists_file)
        config['email_lists'] = config.get('email_lists', {})
        config['email_lists'][list_name] = emails
        self._save_config(self.lists_file, config)
    
    def add_emails_to_list(self, list_name: str, emails: List[Dict]):
        """Add emails to an existing list"""
        config = self._load_config(self.lists_file)
        config['email_lists'] = config.get('email_lists', {})
        
        if list_name not in config['email_lists']:
            config['email_lists'][list_name] = []
        
        # Deduplicate emails
        existing_emails = {email['email'] for email in config['email_lists'][list_name]}
        new_emails = [email for email in emails if email['email'] not in existing_emails]
        
        config['email_lists'][list_name].extend(new_emails)
        self._save_config(self.lists_file, config)
    
    def import_csv_to_list(self, list_name: str, csv_file_path: str):
        """Import emails from CSV file to a list"""
        emails = []
        try:
            with open(csv_file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'email' in row and row['email'].strip():
                        email_data = {
                            'email': row['email'].strip().lower(),
                            'status': 'active'
                        }
                        # Add other columns as additional data
                        for key, value in row.items():
                            if key != 'email' and value.strip():
                                email_data[key] = value.strip()
                        emails.append(email_data)
        except Exception as e:
            print(f"Error importing CSV: {e}")
            return []
        
        self.add_emails_to_list(list_name, emails)
        return emails
    
    # Email Templates Methods
    def get_email_templates(self) -> Dict[str, Dict]:
        """Get all email templates"""
        config = self._load_config(self.templates_file)
        return config.get('email_templates', {})
    
    def get_email_template(self, template_name: str) -> Optional[Dict]:
        """Get a specific email template"""
        templates = self.get_email_templates()
        return templates.get(template_name)
    
    def add_email_template(self, template_name: str, template_config: Dict):
        """Add a new email template"""
        config = self._load_config(self.templates_file)
        config['email_templates'] = config.get('email_templates', {})
        config['email_templates'][template_name] = template_config
        self._save_config(self.templates_file, config)
    
    def render_template(self, template_name: str, variables: Dict[str, str]) -> Optional[Dict]:
        """Render template with variables"""
        template = self.get_email_template(template_name)
        if not template:
            return None
        
        rendered = template.copy()
        
        # Replace variables in subject and body
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            rendered['subject'] = rendered['subject'].replace(placeholder, str(var_value))
            rendered['body'] = rendered['body'].replace(placeholder, str(var_value))
        
        return rendered
    
    # Campaign Methods
    def get_campaigns(self) -> Dict[str, Dict]:
        """Get all campaign configurations"""
        config = self._load_config(self.campaigns_file)
        return config.get('campaigns', {})
    
    def get_campaign(self, campaign_name: str) -> Optional[Dict]:
        """Get a specific campaign configuration"""
        campaigns = self.get_campaigns()
        return campaigns.get(campaign_name)
    
    def add_campaign(self, campaign_name: str, campaign_config: Dict):
        """Add a new campaign configuration"""
        config = self._load_config(self.campaigns_file)
        config['campaigns'] = config.get('campaigns', {})
        config['campaigns'][campaign_name] = campaign_config
        self._save_config(self.campaigns_file, config)
    
    def get_default_settings(self) -> Dict:
        """Get default campaign settings"""
        config = self._load_config(self.campaigns_file)
        return config.get('default_settings', {})
    
    # Utility Methods
    def backup_configs(self) -> str:
        """Create a backup of all configuration files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(f'config_backup_{timestamp}')
        backup_dir.mkdir(exist_ok=True)
        
        config_files = [self.smtp_file, self.lists_file, self.templates_file, self.campaigns_file]
        
        for config_file in config_files:
            if config_file.exists():
                backup_file = backup_dir / config_file.name
                backup_file.write_text(config_file.read_text())
        
        return str(backup_dir)
    
    def get_system_status(self) -> Dict:
        """Get system configuration status"""
        smtp_servers = self.get_smtp_servers()
        enabled_smtp = any(server.get('enabled', False) for server in smtp_servers)
        
        email_lists = self.get_email_lists()
        total_recipients = sum(len(emails) for emails in email_lists.values())
        
        templates = self.get_email_templates()
        campaigns = self.get_campaigns()
        
        return {
            "smtp_configured": enabled_smtp,
            "total_smtp_servers": len(smtp_servers),
            "total_email_lists": len(email_lists),
            "total_recipients": total_recipients,
            "total_templates": len(templates),
            "total_campaigns": len(campaigns),
            "config_files_exist": all([
                self.smtp_file.exists(),
                self.lists_file.exists(),
                self.templates_file.exists(),
                self.campaigns_file.exists()
            ])
        }

# Global instance
config_manager = ConfigManager()