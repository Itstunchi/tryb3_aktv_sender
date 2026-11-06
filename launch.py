#!/usr/bin/env python3
"""
TermSender Pro Enhanced Launcher
Supports both advanced CLI and web UI with SMTP rotation
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional
import webbrowser
import time

from config_manager import config_manager

def launch_web_ui(host='127.0.0.1', port=5000, auto_open=True):
    """Launch the enhanced web UI"""
    print("🚀 Starting TermSender Pro Advanced Web Interface...")
    print(f"📡 Server accessible at: http://localhost:{port}")
    print("🎨 Beautiful dark-themed interface with SMTP rotation")
    print("📊 Real-time analytics and campaign tracking")
    print("🔄 Multiple SMTP server rotation support")
    print("📁 File-based configuration integration")
    print("🔒 Enhanced compliance and security features")
    print("\n" + "="*60)

    if auto_open and port == 5000:
        # Open browser after a short delay
        import threading
        def open_browser():
            time.sleep(2)
            webbrowser.open(f'http://localhost:{port}')

        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()

    # Import and run the enhanced app
    try:
        from app import app
        app.run(host=host, port=port, debug=False)
    except ImportError as e:
        print(f"❌ Error importing app: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting web server: {e}")
        sys.exit(1)

def run_cli_command(command: str, **kwargs):
    """Run CLI commands from the enhanced termsender module"""
    try:
        from termsender import app as cli_app

        # Map commands to CLI functions
        if command == "send":
            # Interactive sending
            cli_app(["send"] + [f"--{k.replace('_', '-')}={v}" for k, v in kwargs.items() if v])
        elif command == "campaign":
            # Run specific campaign
            campaign_name = kwargs.get('name')
            dry_run = kwargs.get('dry_run', True)
            mode = "--dry-run" if dry_run else "--live"
            cli_app(["campaign", campaign_name, mode])
        elif command == "analytics":
            # Show analytics
            cli_app(["analytics"])
        elif command == "config":
            # Show configuration
            cli_app(["config"])
        elif command == "version":
            # Show version
            cli_app(["version"])

    except Exception as e:
        print(f"❌ Error running CLI command: {e}")
        sys.exit(1)

def main():
    """Enhanced main launcher function"""
    parser = argparse.ArgumentParser(
        description="TermSender Pro - Advanced Email Campaign Manager with SMTP Rotation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🚀 ENHANCED FEATURES:
  • Multiple SMTP server rotation (email count or time-based)
  • Real-time analytics and campaign tracking
  • Both web UI and terminal operation modes
  • File-based configuration with JSON configs
  • Advanced rate limiting and delivery optimization

📊 USAGE EXAMPLES:

Web Interface Mode:
  python launch.py                                    # Start beautiful web UI
  python launch.py --web --port 8080                  # Custom port
  python launch.py --web --no-browser                 # Don't auto-open browser

Terminal CLI Mode:
  python launch.py --cli send                         # Interactive email sending
  python launch.py --cli campaign welcome_campaign    # Run specific campaign (test)
  python launch.py --cli campaign welcome_campaign --live  # Run campaign live
  python launch.py --cli analytics                    # View campaign analytics
  python launch.py --cli config                       # Show configurations

Advanced CLI Options:
  python launch.py --cli send --rotation-mode email_count --rotation-value 15
  python launch.py --cli send --rotation-mode time_based --rotation-value 30
  python launch.py --cli send --smtp-config "Gmail Primary" --delay 2.0

📁 FILE-BASED CONFIGURATION:
  Edit these files to pre-configure campaigns:
  • config/smtp_servers.json      # Multiple SMTP servers with rotation
  • config/email_lists.json       # Recipient lists with metadata
  • config/email_templates.json   # Reusable email templates
  • config/campaign_settings.json # Pre-configured campaigns

🔄 SMTP ROTATION MODES:
  • email_count: Rotate after N emails (e.g., every 10 emails)
  • time_based: Rotate after N seconds (e.g., every 30 seconds)

📊 ANALYTICS FEATURES:
  • Real-time sending progress with SMTP tracking
  • Success/failure rates per SMTP server
  • Campaign history and performance metrics
  • Detailed failure analysis and retry logging
        """
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--web', action='store_true', default=True,
                          help='Start web UI (default)')
    mode_group.add_argument('--cli', type=str, metavar='COMMAND',
                          choices=['send', 'campaign', 'analytics', 'config', 'version'],
                          help='Run CLI command: send, campaign, analytics, config, version')

    # Web UI options
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host to bind web server (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000,
                       help='Port for web server (default: 5000)')
    parser.add_argument('--no-browser', action='store_true',
                       help="Don't automatically open browser")

    # CLI options
    parser.add_argument('--campaign-name', type=str,
                       help='Campaign name for CLI campaign command')
    parser.add_argument('--live', action='store_true',
                       help='Run campaign in live mode (default: dry-run)')
    parser.add_argument('--smtp-config', type=str,
                       help='SMTP configuration name')
    parser.add_argument('--email-list', type=str,
                       help='Email list name')
    parser.add_argument('--template', type=str,
                       help='Email template name')
    parser.add_argument('--rotation-mode', type=str, choices=['email_count', 'time_based'],
                       default='email_count', help='SMTP rotation mode')
    parser.add_argument('--rotation-value', type=int, default=10,
                       help='Emails per rotation or seconds per rotation')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay between emails in seconds')

    args = parser.parse_args()

    # Print enhanced banner
    print("\n" + "="*70)
    print("  TermSender Pro v3.0 - Advanced Email Campaign Manager")
    print("  🎨 Beautiful Web UI + 🔄 SMTP Rotation + 📊 Analytics")
    print("  🖥️  Terminal CLI + 📁 File-based Configuration")
    print("="*70)

    # Execute based on mode
    if args.cli:
        # CLI mode with enhanced options
        cli_kwargs = {
            'smtp_config': args.smtp_config,
            'email_list': args.email_list,
            'template': args.template,
            'rotation_mode': args.rotation_mode,
            'rotation_value': args.rotation_value,
            'delay': args.delay,
            'dry_run': not args.live,
            'interactive': True
        }

        # Special handling for campaign command
        if args.cli == 'campaign':
            if not args.campaign_name:
                print("❌ --campaign-name is required for campaign command")
                sys.exit(1)
            cli_kwargs['name'] = args.campaign_name

        run_cli_command(args.cli, **cli_kwargs)
    else:
        # Default to enhanced web UI
        auto_open = not args.no_browser
        launch_web_ui(args.host, args.port, auto_open)

if __name__ == '__main__':
    main()
