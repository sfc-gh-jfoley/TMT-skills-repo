# Publishing Cortex Code Skills as Remote Profiles

## Quick Start (Ask Cortex Code)

Just paste this into Cortex Code, replacing the path:

```
Publish the skill at /path/to/my-skill as a remote profile on Snowhouse. Use these steps:

1. Publish the skill to stage: cortex skill publish <skill-path> --to-stage "@TEMP.VSHIV.SKILLS/" --connection SNOWHOUSE_SE

2. Create a profile JSON at /tmp/ with the skill name and description from the SKILL.md frontmatter, ownerTeam "SE", and skillRepos pointing to "@TEMP.VSHIV.SKILLS/<skill-directory-name>"

3. Publish the profile: cortex profile publish <name> --from-file <json> --description "<desc>" --owner-team "SE" --skill-stage "@TEMP.VSHIV.SKILLS/<skill-directory-name>" --version "1.0.0" --connection SNOWHOUSE_SE
4. Verify with: cortex profile list-remote -c SNOWHOUSE_SE | grep <name>
```

## Manual Steps (Reference)

### Prerequisites

- Cortex Code CLI installed
- A Snowflake connection with write access to a stage (e.g., `SNOWHOUSE_SE`)

### 1. Create a Stage (one-time)

```sql
CREATE STAGE IF NOT EXISTS TEMP.VSHIV.SKILLS;
```

### 2. Publish Skill to Stage

```bash
cortex skill publish /path/to/your-skill-directory \
  --to-stage "@TEMP.VSHIV.SKILLS/" \
  --connection SNOWHOUSE_SE
```

This uploads `SKILL.md` (and any subdirectories like `references/`, `templates/`) to the stage.

### 3. Create a Profile JSON

Save to `/tmp/my-profile.json`:

```json
{
  "name": "my-skill-name",
  "description": "What this skill does and when to use it.",
  "ownerTeam": "SE",
  "skillRepos": [
    {
      "snowflake_stage": "@TEMP.VSHIV.SKILLS/your-skill-directory"
    }
  ],
  "mcpServers": {},
  "commandRepos": [],
  "scripts": [],
  "hooks": null,
  "plugins": [],
  "envVars": {},
  "settingsOverrides": {},
  "version": "1.0.0"
}
```

### 4. Publish the Profile

```bash
cortex profile publish my-skill-name \
  --from-file /tmp/my-profile.json \
  --description "Your skill description" \
  --owner-team "SE" \
  --skill-stage "@TEMP.VSHIV.SKILLS/your-skill-directory" \
  --version "1.0.0" \
  --connection SNOWHOUSE_SE
```

### 5. Verify

```bash
cortex profile list-remote -c SNOWHOUSE_SE
```

## For Users: How to Use a Published Profile

```bash
# Browse available profiles
cortex profile list-remote -c SNOWHOUSE_SE

# Add a profile (one-time)
cortex profile add <profile-name> -c SNOWHOUSE_SE

# Launch with the profile
cortex --profile <profile-name>
```

## Updating a Skill

Re-publish the skill to the same stage, then bump the profile version:

```bash
# Upload updated files
cortex skill publish /path/to/your-skill-directory \
  --to-stage "@TEMP.VSHIV.SKILLS/" \
  --connection SNOWHOUSE_SE

# Publish new version
cortex profile publish my-skill-name \
  --from-file /tmp/my-profile.json \
  --version "1.1.0" \
  --connection SNOWHOUSE_SE
```

Users pull the update with:

```bash
cortex profile sync <profile-name>
```

## Currently Published Profiles

| Profile | Skill Stage Path | Version |
|:--------|:-----------------|:--------|
| `account-360` | `@TEMP.VSHIV.SKILLS/a360-coco-skill` | 1.0.0 |
| `snowflake-user-analysis` | `@TEMP.VSHIV.SKILLS/snowflake-user-analytics-coco-skill` | 1.0.0 |
| `snowflake-intelligence-accelerator-via-snowhouse` | `@TEMP.VSHIV.SKILLS/snowflake-intelligence-accelerator-via-snowhouse` | 1.0.0 |

## Notes

- Users need read access to the `TEMP.VSHIV.SKILLS` stage on Snowhouse
- The `name` and `description` in the profile JSON should match the SKILL.md frontmatter
- The `--skill-stage` flag in `cortex profile publish` should point to the specific skill subdirectory, not the root stage
