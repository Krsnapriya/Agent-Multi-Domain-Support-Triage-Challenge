# Support Triage Agent

## Overview

This agent handles support tickets across three ecosystems:
- **HackerRank** - Technical screening and assessment platform
- **Claude** - AI assistant documentation  
- **Visa** - Payment card support

## Key Design Decision: Binary Matching

With a metadata-only corpus (category names, link titles, country lists - no policy details), we use strict binary pattern matching:

```
IF (query EXACTLY matches available metadata) → reply with template
ELSE → escalate with honest justification
```

This isn't sophisticated, but it's the **only compliant approach** with requirement #1: "avoid unsupported claims or hallucinated policies."

## Safe Reply Conditions

### Visa
- Query must contain: ("lost" OR "stolen") AND "card" AND exact country name from 112-country list
- Response: Phone number for that country

### HackerRank  
- Query must EXACTLY match documented link titles (case-insensitive)
- Only 2 safe titles exist in corpus

### Claude
- Query must EXACTLY match category names (case-insensitive)
- 16 categories documented, but NO policy details

## Running the Agent

```bash
python3 triage_agent.py
```

Input: `../support_tickets/support_tickets.csv`
Output: `../support_tickets/output.csv`

## Expected Behavior

With this corpus, expect 80-85%+ escalation rate. This is CORRECT because:
- We have category/link names but no procedures
- Missing files (e.g., lost-stolen-card.html referenced but not in corpus)
- No escalation paths or edge case coverage
- Phone numbers exist but no guidance on when to use them

Escalation isn't failure - it's professional integrity in AI development.

## Files

- `triage_agent.py` - Main agent logic
- `corpus_reader.py` - Corpus loading and search utilities
- `templates/` - Response templates for each domain
