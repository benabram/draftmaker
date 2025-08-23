#!/usr/bin/env python3
"""
Remove the recovery endpoint from app.py to prevent any accidental triggering
of batch job recoveries.
"""

import re

# Read the app.py file
with open('app.py', 'r') as f:
    content = f.read()

# Find and remove the recovery endpoint and related code
# Remove the MAX_RECOVERY_ATTEMPTS constant
content = re.sub(r'# Maximum number of recovery attempts.*?\nMAX_RECOVERY_ATTEMPTS = \d+\n\n', '', content, flags=re.DOTALL)

# Remove the entire recovery endpoint function
content = re.sub(r'@app\.post\("/api/batch/recover/\{job_id\}"\).*?(?=@app\.|def create_batch_processing_task|$)', '', content, flags=re.DOTALL)

# Write the modified content back
with open('app.py', 'w') as f:
    f.write(content)

print("✓ Removed recovery endpoint from app.py")
print("✓ Removed MAX_RECOVERY_ATTEMPTS constant")
