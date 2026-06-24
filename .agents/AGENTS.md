# Workspace Rules & Instructions

This directory (`.agents`) is the customization root for **Antigravity**. It maps and references the core EM workflow instructions, rules, and runbooks located under the `.cursor` folder.

## Core Reference Manifest
For the complete package structure, 5-step process pipeline, snapshot tables, and execution instructions:
- Refer to [WORKFLOW.md](file:///Users/easygautam/Documents/Sprint-Automation/.cursor/WORKFLOW.md)

## Active Rules & Constraints
Please refer to the following active rules for full context and instructions before performing any action:

1. **EM Workflow Rules:**
   - Triggers, CLI parameters, and output paths are defined in [em-workflow.mdc](file:///Users/easygautam/Documents/Sprint-Automation/.cursor/rules/em-workflow.mdc)
2. **Schedule Engine Rules & Constants:**
   - Hours per day, priority sorting, team mappings, and issue classifications are defined in [schedule-engine.mdc](file:///Users/easygautam/Documents/Sprint-Automation/.cursor/rules/schedule-engine.mdc)
3. **Jira Read-Only Access:**
   - Allowed and forbidden Jira operations, permissions, and safeguards are defined in [jira-read-only.mdc](file:///Users/easygautam/Documents/Sprint-Automation/.cursor/rules/jira-read-only.mdc)

## Custom Agents & Runbooks
The agent configurations and workflow runbooks are registered under:
- **Sprint Analyst Agent:** [sprint-analyst.md](file:///Users/easygautam/Documents/Sprint-Automation/.cursor/agents/sprint-analyst.md)
- **Sprint Report Skill:** [SKILL.md](file:///Users/easygautam/Documents/Sprint-Automation/.cursor/skills/sprint-report/SKILL.md)
- **Epic Estimation Skill:** [SKILL.md](file:///Users/easygautam/Documents/Sprint-Automation/.cursor/skills/epic-estimation/SKILL.md)
- **Epic Slack Integration:** [SKILL.md](file:///Users/easygautam/Documents/Sprint-Automation/.cursor/skills/epic-estimation-send-slack/SKILL.md)
- **Jira Domain Mapping:** [SKILL.md](file:///Users/easygautam/Documents/Sprint-Automation/.cursor/skills/jira-domain/SKILL.md)
