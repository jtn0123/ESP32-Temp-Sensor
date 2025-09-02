#!/usr/bin/env python3
"""
Security audit for staged files only - used by pre-commit hook.
Only scans files that are about to be committed.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# Severity levels
class Severity:
    CRITICAL = "CRITICAL"  # Passwords, API keys
    HIGH = "HIGH"         # Potential secrets
    MEDIUM = "MEDIUM"     # Private IPs
    LOW = "LOW"           # Warnings

# Credential patterns with severity
CREDENTIAL_PATTERNS = [
    # CRITICAL - Actual passwords/keys
    (Severity.CRITICAL, r'password\s*[=:]\s*["\'][a-zA-Z0-9!@#$%^&*()]{6,}["\']', "Password with value"),
    (Severity.CRITICAL, r'api[_-]?key\s*[=:]\s*["\'][a-zA-Z0-9]{32,}["\']', "API key"),
    (Severity.CRITICAL, r'token\s*[=:]\s*["\'][a-zA-Z0-9]{20,}["\']', "Token"),
    (Severity.CRITICAL, r'secret\s*[=:]\s*["\'][a-zA-Z0-9]{16,}["\']', "Secret"),
    
    # HIGH - Potential credentials
    (Severity.HIGH, r'mqtt[_-]?pass\s*[=:]\s*["\'][^"\']+["\']', "MQTT password"),
    (Severity.HIGH, r'wifi[_-]?pass\s*[=:]\s*["\'][^"\']+["\']', "WiFi password"),
    
    # MEDIUM - Network config (less critical)
    (Severity.MEDIUM, r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', "Private IP (10.x)"),
    (Severity.MEDIUM, r'\b192\.168\.\d{1,3}\.\d{1,3}\b', "Private IP (192.168.x)"),
    (Severity.MEDIUM, r'\b172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}\b', "Private IP (172.x)"),
    
    # LOW - Warnings
    (Severity.LOW, r'ssid\s*[=:]\s*["\'][^"\']+["\']', "WiFi SSID"),
]

# Files/patterns that are allowed to have these patterns
EXCLUSIONS = {
    # File-based exclusions
    'files': {
        '.env.example': [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW],
        'device.sample.yaml': [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW],
        'security_audit.py': [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW],
        'security_audit_staged.py': [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW],
        'PRODUCTION_IMPROVEMENTS.md': [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM],
        'README.md': [Severity.MEDIUM, Severity.LOW],
    },
    # Path patterns
    'path_patterns': {
        'test_': [Severity.MEDIUM, Severity.LOW],  # Test files can have example IPs
        'tests/': [Severity.MEDIUM, Severity.LOW],
        'fixtures/': [Severity.MEDIUM, Severity.LOW],
        '.example': [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW],
        '.sample': [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW],
        'docs/': [Severity.MEDIUM, Severity.LOW],  # Documentation can have example IPs
        'scripts/rotate_credentials': [Severity.MEDIUM],  # This script mentions IPs
    },
    # Content patterns that indicate it's an example
    'content_indicators': [
        'your_password',
        'YOUR_PASSWORD',
        'example',
        'changeme',
        'placeholder',
        '<password>',
        '${',  # Template variable
    ]
}

def get_staged_files():
    """Get list of files staged for commit."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True,
            text=True,
            check=True
        )
        return [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
    except subprocess.CalledProcessError:
        return []

def is_excluded(filepath, severity, content=None):
    """Check if a finding should be excluded."""
    filename = os.path.basename(filepath)
    
    # Check file-based exclusions
    if filename in EXCLUSIONS['files']:
        if severity in EXCLUSIONS['files'][filename]:
            return True
    
    # Check path pattern exclusions
    for pattern, severities in EXCLUSIONS['path_patterns'].items():
        if pattern in filepath and severity in severities:
            return True
    
    # Check content indicators (for HIGH/CRITICAL only)
    if content and severity in [Severity.CRITICAL, Severity.HIGH]:
        for indicator in EXCLUSIONS['content_indicators']:
            if indicator.lower() in content.lower():
                return True
    
    return False

def check_file_for_credentials(filepath):
    """Check a single file for credentials."""
    findings = []
    
    if not os.path.exists(filepath):
        return findings
    
    # Skip binary files
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return findings
    
    lines = content.split('\n')
    
    for severity, pattern, description in CREDENTIAL_PATTERNS:
        for i, line in enumerate(lines, 1):
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                # Check if this should be excluded
                if not is_excluded(filepath, severity, match.group()):
                    findings.append({
                        'file': filepath,
                        'line': i,
                        'severity': severity,
                        'description': description,
                        'match': match.group()[:50] + '...' if len(match.group()) > 50 else match.group()
                    })
    
    return findings

def main():
    """Main function."""
    print("🔍 Scanning staged files for credentials...")
    
    # Get staged files
    staged_files = get_staged_files()
    
    if not staged_files:
        print("  ✅ No files staged for commit")
        return 0
    
    print(f"  Checking {len(staged_files)} staged files...")
    
    # Check each staged file
    all_findings = []
    for filepath in staged_files:
        # Skip certain file types
        if filepath.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz')):
            continue
        
        findings = check_file_for_credentials(filepath)
        all_findings.extend(findings)
    
    # Group findings by severity
    critical = [f for f in all_findings if f['severity'] == Severity.CRITICAL]
    high = [f for f in all_findings if f['severity'] == Severity.HIGH]
    medium = [f for f in all_findings if f['severity'] == Severity.MEDIUM]
    low = [f for f in all_findings if f['severity'] == Severity.LOW]
    
    # Report findings
    if critical or high:
        print("\n🚨 SECURITY ISSUES FOUND:")
        
        if critical:
            print(f"\n  CRITICAL ({len(critical)} issues):")
            for f in critical[:5]:
                print(f"    {f['file']}:{f['line']} - {f['description']}: {f['match']}")
            if len(critical) > 5:
                print(f"    ... and {len(critical) - 5} more")
        
        if high:
            print(f"\n  HIGH ({len(high)} issues):")
            for f in high[:5]:
                print(f"    {f['file']}:{f['line']} - {f['description']}: {f['match']}")
            if len(high) > 5:
                print(f"    ... and {len(high) - 5} more")
        
        print("\n❌ COMMIT BLOCKED: Critical or high severity issues found")
        print("\nTo fix:")
        print("  1. Remove credentials from files")
        print("  2. Use environment variables or .env")
        print("  3. Stage your changes again")
        print("\nTo bypass (NOT RECOMMENDED):")
        print("  git commit --no-verify")
        
        return 1
    
    # Only warnings
    if medium or low:
        print("\n⚠️  Warnings found (commit will proceed):")
        
        if medium:
            print(f"  MEDIUM: {len(medium)} issues (private IPs, etc.)")
            for f in medium[:2]:
                print(f"    {f['file']} - {f['description']}")
        
        if low:
            print(f"  LOW: {len(low)} issues (SSIDs, etc.)")
        
        print("\n  ℹ️  Review these warnings but commit is allowed")
    else:
        print("  ✅ No security issues found in staged files")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())