---
description: Check grant proposal status, lint results, and submission readiness
---

# Grant status check

You are helping the user check the status of their grant proposal.

## Instructions

1. Find the grant directory:
   - Look for `grant.yaml` in the current or parent directories.
   - Identify the funder and program from `grant.yaml`.

2. Show completion and word counts:
   ```bash
   grantkit status
   ```

3. Run the linter:
   ```bash
   grantkit check
   ```

4. Summarize for the user:
   - Completion % and deadline countdown.
   - Word counts per section vs. their limits.
   - Any errors (must fix before submission) vs. warnings.
   - What's complete vs. what's still empty or partial.

5. If there are errors or warnings, suggest specific next steps, section by
   section.

## Arguments

- `$1` = path to the grant directory (optional, defaults to `.`).
