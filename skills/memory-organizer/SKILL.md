# Memory Organizer Skill

Organize and maintain the /memories directory for optimal retrieval and reduced clutter.

## Triggers
- "organize memories", "clean up memories", "memory audit", "consolidate memories"

## Workflow

### Phase 1: Audit Current State
1. View `/memories` directory structure
2. Read ALL memory files to understand content
3. Create analysis table:

| File | Category | Status | Size | Last Updated |
|------|----------|--------|------|--------------|
| ... | Meta/Project/Reference/Archive | Active/Stale/Complete | lines | date |

### Phase 2: Identify Issues
Check for:
- **Duplicates**: Same content in multiple files
- **Completed projects**: Tasks marked COMPLETE that can be archived
- **Oversized files**: Files mixing multiple unrelated topics
- **Missing index**: No INDEX.md or outdated index
- **Stale content**: References to old paths, deprecated syntax, etc.

### Phase 3: Propose Structure
Standard organization:
```
/memories/
├── INDEX.md                    # Master index (REQUIRED)
├── SESSION_PROTOCOL.md         # Session start/end checklists
├── <topic>_learnings.md        # Technical reference by topic
├── skills_inventory.md         # Installed skills tracking
├── projects/
│   ├── active/                 # Current work
│   │   └── <project>.md
│   └── archive/                # Completed work (condensed)
│       └── <project>.md
```

### Phase 4: Execute Reorganization
1. Create INDEX.md with links to all files
2. Split oversized files by topic
3. Move completed projects to archive (condense to essentials)
4. Remove duplicate content
5. Delete obsolete files

### Phase 5: Validate
1. View final `/memories` structure
2. Confirm INDEX.md is accurate
3. Verify no orphaned references

## INDEX.md Template
```markdown
# Memory Index
Last organized: YYYY-MM-DD

## Quick Reference
| File | Purpose | Check When |
|------|---------|------------|
| [SESSION_PROTOCOL.md](SESSION_PROTOCOL.md) | Session checklists | Every session |
| ... | ... | ... |

## Active Projects
| File | Description |
|------|-------------|
| [projects/active/X.md](projects/active/X.md) | ... |

## Archived Projects
| File | Completed | Summary |
|------|-----------|---------|
| [projects/archive/X.md](projects/archive/X.md) | YYYY-MM-DD | ... |
```

## Archive Guidelines
When archiving completed projects, keep only:
- Project location/identifiers
- Key commands or patterns to reuse
- Final deliverables summary
- Lessons learned (if any)

Remove:
- Step-by-step progress logs
- Debugging notes
- Intermediate findings

## Maintenance Schedule
- Run audit monthly or when memories exceed 10 files
- Archive projects within 1 week of completion
