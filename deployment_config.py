#!/usr/bin/env python3
"""
Deployment Configuration for TermSender Pro
Sets up production-ready Flask application
"""

import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

def create_production_app():
    """Create Flask app configured for production deployment"""
    
    # Import the main app
    from app import app
    
    # Production configurations
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY') or os.urandom(32),
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=3600,  # 1 hour
        MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100MB max file size
        
        # Security headers
        SEND_FILE_MAX_AGE_DEFAULT=31536000,  # 1 year for static files
    )
    
    # Handle proxy headers for deployed applications
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Add security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; script-src 'self' 'unsafe-inline'"
        return response
    
    return app

def setup_logging():
    """Set up production logging"""
    import logging
    from logging.handlers import RotatingFileHandler
    
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    file_handler = RotatingFileHandler('logs/termsender.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    
    app = create_production_app()
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('TermSender Pro startup')
    
    return app

if __name__ == '__main__':
    # For production deployment
    app = setup_logging()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
