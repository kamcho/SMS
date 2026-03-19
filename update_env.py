#!/usr/bin/env python3
"""
Script to update .env file with ngrok callback URLs
"""

import os
from pathlib import Path

# Path to .env file
env_file = Path('.env')

# Read current .env content
if env_file.exists():
    with open(env_file, 'r') as f:
        content = f.read()
else:
    print("❌ .env file not found!")
    exit(1)

# Define the ngrok URL
ngrok_url = "https://arhythmically-unciliated-danna.ngrok-free.dev"

# Lines to update
updates = {
    'MPESA_CALLBACK_URL': f'{ngrok_url}/accounts/mpesa/callback/',
    'MPESA_RESULT_URL': f'{ngrok_url}/accounts/mpesa/result/',
    'MPESA_QUEUE_TIMEOUT_URL': f'{ngrok_url}/accounts/mpesa/timeout/'
}

# Update content
lines = content.split('\n')
updated_lines = []

for line in lines:
    updated = False
    for key, value in updates.items():
        if line.startswith(f'{key}='):
            updated_lines.append(f'{key}={value}')
            updates.pop(key)  # Remove from updates dict
            updated = True
            break
    
    if not updated:
        updated_lines.append(line)

# Add any remaining new keys
for key, value in updates.items():
    updated_lines.append(f'{key}={value}')

# Write back to .env
with open(env_file, 'w') as f:
    f.write('\n'.join(updated_lines))

print("✅ Updated .env file with ngrok URLs:")
print(f"   MPESA_CALLBACK_URL={ngrok_url}/accounts/mpesa/callback/")
print(f"   MPESA_RESULT_URL={ngrok_url}/accounts/mpesa/result/")
print(f"   MPESA_QUEUE_TIMEOUT_URL={ngrok_url}/accounts/mpesa/timeout/")
print("\n🔄 Please restart your Django server to apply changes!")
