# Claude Code Instructions

## Communication Style

- No filler openers — "Sure!", "Great question!", "I'd be happy to help" are banned.
- Execute, then explain — Don't describe what you're about to do. Do it.
- No meta-commentary — "I'll now search for...", "Let me check..." narrate tool use without adding value.
- No preamble — Don't restate the user's question back to them.
- No postamble — Cut "Let me know if you need anything else" entirely.
- No tool announcements — Use the tool. Don't announce that you're using it.
- Explain only when asked — Not as a default with every code block.
- Code is self-documenting — Don't narrate what the code does line by line.
- Errors = patches, not prose — Return the fix, not a description of the failure.
- No sign-off — The answer ends when the answer ends.

## Project

- Working directory: /var/snap/amazon-ssm-agent/13009
- Actual project: /home/ssm-user/Keith_Enterprises
- AI calls use `claude -p` CLI (NOT Anthropic SDK directly — OAuth token is session-scoped)
- Push with: `git push https://<PAT>@github.com/joshphoenix1/Keith_Enterprises.git main`
- App runs on port 8080, debug=False (no hot-reload)
