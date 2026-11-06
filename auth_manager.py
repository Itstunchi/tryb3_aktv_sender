#!/usr/bin/env python3
"""
Authentication Manager for TermSender Pro
Handles license key validation and user authentication
"""

import json
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from flask import session

class AuthManager:
    def __init__(self):
        self.config_dir = Path('config')
        self.license_file = self.config_dir / 'license_keys.json'
        self._initialize_license_file()
        
    def _initialize_license_file(self):
        """Initialize license file if it doesn't exist"""
        if not self.license_file.exists():
            with open(self.license_file, 'w') as f:
                json.dump({"license_keys": []}, f, indent=2)
    
    def _hash_key(self, key):
        """Hash a license key for secure storage"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def validate_key(self, license_key):
        """Validate a license key against the database"""
        key_hash = self._hash_key(license_key)
        
        with open(self.license_file, 'r') as f:
            data = json.load(f)
        
        for key_data in data['license_keys']:
            if key_data['key_hash'] == key_hash and key_data['is_active']:
                # Check if key is expired
                if 'expiry_date' in key_data:
                    expiry = datetime.strptime(key_data['expiry_date'], '%Y-%m-%d')
                    if expiry < datetime.now():
                        return False, "License key has expired"
                
                # Update last login time
                self._update_last_login(key_hash)
                
                # Store user info in session
                session['authenticated'] = True
                session['user_email'] = key_data.get('user_email')
                session['user_name'] = key_data.get('user_name')
                
                return True, "Authentication successful"
        
        return False, "Invalid license key"
    
    def _update_last_login(self, key_hash):
        """Update the last login timestamp for a key"""
        with open(self.license_file, 'r') as f:
            data = json.load(f)
        
        for key_data in data['license_keys']:
            if key_data['key_hash'] == key_hash:
                key_data['last_login'] = datetime.now().isoformat()
        
        with open(self.license_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def generate_key(self, user_email, user_name, expiry_days=365):
        """Generate a new license key"""
        # Generate a random key
        key = '-'.join([''.join(os.urandom(4).hex()[:4]) for _ in range(4)]).upper()
        key_hash = self._hash_key(key)
        
        # Create expiry date
        created = datetime.now()
        expiry = created + timedelta(days=max(1, int(expiry_days)))
        
        # Add to database
        with open(self.license_file, 'r') as f:
            data = json.load(f)
        
        data['license_keys'].append({
            "key_hash": key_hash,
            "user_email": user_email,
            "user_name": user_name,
            "created_date": created.strftime('%Y-%m-%d'),
            "expiry_date": expiry.strftime('%Y-%m-%d'),
            "is_active": True,
            "last_login": None
        })
        
        with open(self.license_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        return key
    
    def is_authenticated(self):
        """Check if the current session is authenticated"""
        return session.get('authenticated', False)
    
    def logout(self):
        """Clear the authentication session"""
        session.pop('authenticated', None)
        session.pop('user_email', None)
        session.pop('user_name', None)
    
    def get_all_keys(self):
        """Get all license keys (admin function)"""
        with open(self.license_file, 'r') as f:
            data = json.load(f)
        return data['license_keys']
    
    def deactivate_key(self, user_email):
        """Deactivate a license key by user email"""
        with open(self.license_file, 'r') as f:
            data = json.load(f)
        
        for key_data in data['license_keys']:
            if key_data['user_email'] == user_email:
                key_data['is_active'] = False
        
        with open(self.license_file, 'w') as f:
            json.dump(data, f, indent=2)

# Create a singleton instance
auth_manager = AuthManager()
