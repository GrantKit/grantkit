---
description: Generate simulated NSF panel reviews for a grant proposal
---

# Simulate NSF Panel Review

You are helping the user get simulated panel reviews for their NSF grant proposal.

## Instructions

1. First, find and read the grant proposal:
   - Look for `grant.yaml` in the current directory or parent directories
   - Read `assembled_proposal.md` if it exists
   - Otherwise, read files from the `responses/` directory

2. Identify the NSF program from `grant.yaml` (e.g., CSSI Elements, POSE, CAREER)

3. Generate 3-4 simulated reviewer profiles appropriate for the program:
   - Each reviewer should have distinct expertise and concerns
   - Include at least one domain expert, one technical reviewer, and one impact-focused reviewer

4. For each reviewer, generate a complete NSF-style review including:
   - Summary of the proposal
   - Intellectual Merit assessment (strengths and weaknesses)
   - Broader Impacts assessment (strengths and weaknesses)
   - Rating (Excellent/Very Good/Good/Fair/Poor)

5. Conclude with a Panel Summary:
   - Table of reviewers, ratings, and key concerns
   - Overall assessment
   - Suggested revisions

## Output Format

Use the NSF review format with clear sections. Be constructively critical--the goal is to help improve the proposal before submission.

If arguments are provided:
- `$1` = path to grant directory (optional, defaults to current directory)
