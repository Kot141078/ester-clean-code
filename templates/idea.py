"""Template notes for context-window UX behavior.

This file stores product notes in a Python-safe format so it can be imported
or linted without syntax errors.
"""

IDEA_NOTES = """
1) Context boundary management (warn in advance, do not "jump" silently)

What is needed:
- A live token counter with two thresholds: WARN (for example, <15% left)
  and HARD (<5%).
- Before WARN, show a lightweight banner/toast and a short "ping" sound in
  voice mode.
- User choice buttons:
  1. "Summarize and continue" (auto-summary -> carry over to a new session),
  2. "Start a clean session",
  3. "Fit into current session" (compact tail history: remove/compact).
- For voice input: do not start a new session while the user is speaking;
  wait until speech is complete, then show the modal. If speech recognition
  is available, buffer first and present the three options after capture.

Monitoring core pseudocode:

```python
class ContextBudget:
    def __init__(self, max_tokens: int, warn_ratio: float = 0.85, hard_ratio: float = 0.95):
        self.max = max_tokens
        self.warn = int(max_tokens * warn_ratio)
        self.hard = int(max_tokens * hard_ratio)

    def remaining(self, used: int) -> int:
        return max(self.max - used, 0)

    def state(self, used: int) -> str:
        r = self.remaining(used)
        if r <= self.hard:
            return "HARD"
        if r <= self.warn:
            return "WARN"
        return "OK"
```
"""
