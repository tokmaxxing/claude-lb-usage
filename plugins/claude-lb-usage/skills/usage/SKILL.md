---
name: usage
description: Show this customer's live claude-lb API-key usage, remaining limits, and reset times.
disable-model-invocation: true
---

## Live claude-lb usage

!`"${CLAUDE_PLUGIN_ROOT}/bin/claude-lb-usage" --full`

Return the live usage output above verbatim. Do not infer missing limits or substitute upstream account quota.
