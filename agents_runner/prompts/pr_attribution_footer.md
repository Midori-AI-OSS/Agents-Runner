# PR Attribution Footer

This footer is appended to PR descriptions to attribute work to Midori AI Agents Runner.

**When used:** When creating or updating pull requests via the gh CLI integration  
**Template variables:**
- `{agent_used}` - The formatted agent name without CLI flags (or "(unknown)")
- `{agents_runner_url}` - URL to the Midori AI Agents Runner repository
- `{midoriai_url}` - URL to the Midori AI monorepo
- `{marker}` - HTML comment marker to prevent duplicate footers

## Prompt
---
{marker}
Created by [Midori AI Agents Runner]({agents_runner_url})
Agent Used: {agent_used}
Related: [Midori AI Monorepo]({midoriai_url})

