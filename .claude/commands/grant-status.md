---
description: Check grant proposal status, validation, and submission checklist
---

# Grant Status Check

You are helping the user check the status of their NSF grant proposal.

## Instructions

1. Find the grant directory:
   - Look for `grant.yaml` in current or parent directories
   - Identify the NSF program

2. Run validation:
   ```bash
   grantkit validate
   ```

3. Show the checklist:
   ```bash
   grantkit checklist
   ```

4. Summarize:
   - Word counts per section vs limits
   - Any validation errors or warnings
   - What's complete vs what's missing
   - Deadline status

5. If there are issues, suggest specific next steps

## Arguments
- `$1` = path to grant directory (optional)
