# Jira best practices for sprint

How to structure issues, titles, estimates, and dates in Jira during a sprint. Follow these rules so delivery work stays consistent across Backend, Web, Mobile, and QA.

---

## Required on every issue

| What | Action |
|------|--------|
| **Sprint** | Add the issue to the **active sprint** |
| **Epic link** | Link tasks and bugs to the correct **Epic** (via Story parent or direct parent) |
| **Assignee** | Set the person doing the work |
| **Summary** | Use the title rules in this doc (`BE \|`, `WEB \|`, `APP \|`, `QA \|`, or `Leave \|`) |

**Tasks and Sub-tasks:** set **Original Estimate** when the work is ready to plan.

**Bugs (when fixed):** log **Time spent** on the worklog.

---

## Issue types

| Type | Use for |
|------|---------|
| **Epic** | One PRD or delivery |
| **Story** | Releasable slice under an epic |
| **Task / Sub-task** | Build, QA, leave, and other execution work |
| **Bug** | Defects only |

Do not log features or enhancements as **Bug**. Use **Task** or **Sub-task**.

---

## Platform prefixes (BE, WEB, APP only)

For Backend, Web, and Mobile work, the **first part of the summary before `|`** must be:

| Prefix | Platform |
|--------|----------|
| **BE** | Backend |
| **WEB** | Web |
| **APP** | Mobile |

Use **BE**, **WEB**, and **APP** everywhere — assessment, development, bugs (when you want a clear platform), and release-related work.

**QA** titles always start with **`QA |`**. Add **WEB**, **APP**, or **BE** in the title when the work is for one platform (see [QA titles](#qa-titles)).

Prefixes are case-insensitive in Jira (`be |` works), but always write **BE**, **WEB**, and **APP**.

### Title pattern

```
{PREFIX} | {short description}
```

Examples:

```
BE | Assessment
WEB | Assessment
APP | Assessment
BE | Add coupon API
WEB | Checkout flow refactor
APP | Registration funnel UI
```

### Do not use as the first prefix

| Avoid | Use instead |
|-------|-------------|
| `Backend \| Assessment` | `BE \| Assessment` |
| `Android \| Assessment` | `APP \| Assessment` |
| `Stage-APP \| Icon wrong` | `APP \| Icon wrong` or `WEB \| …` |
| `Enhancement: …` (no pipe) | `BE \| Enhancement: …` |

---

## QA titles

All QA work starts with **`QA |`** and **must** include a platform in the **second** pipe segment.

| Segment 2 | Platform |
|-----------|----------|
| `WEB` | Web |
| `APP` | Mobile |
| `BE` | Backend |

Titles without a platform (e.g. `QA | Assessment`, `QA | Test cases — Events`) are **unmapped** and flagged in data quality.

### QA Assessment / Test Planning

Per-platform test planning (maps to **QA Test Planning** on that platform’s execution table):

```
QA | App | Assessment / Test Planning
QA | Web | Assessment
QA | BE | Assessment
```

### QA Execution

Default execution work (maps to **Stage testing** on that platform):

```
QA | App | events PRD e2e
QA | Web | events PRD e2e
QA | BE | API testing
```

### QA Automation

Automation work (maps to **Stage testing** on that platform):

```
QA | BE | Automation | integrate events PRD API automation
QA | App | Automation | NSAT test attempts flow automation
QA | Web | Automation | NSAT test attempts flow automation
```

---

## Delivery phases — what to create in Jira

### Tech Solutioning (dev assessment)

Create a **Task** or **Sub-task** under the epic:

| Platform | Summary |
|----------|---------|
| Backend | `BE \| Assessment` |
| Web | `WEB \| Assessment` |
| Mobile | `APP \| Assessment` |

Maps to **Tech Solutioning** on that platform’s execution table.

### QA Test Planning

| Platform | Summary example |
|----------|-----------------|
| Backend | `QA \| BE \| Assessment` |
| Web | `QA \| WEB \| Assessment` |
| Mobile | `QA \| APP \| Assessment` |

Set **Original Estimate**, **Assignee**, and add to the sprint.

### Development

Use **BE \|**, **WEB \|**, or **APP \|** for build work (not assessment, pre-prod, UAT, or leave):

```
BE | Scholarship upload API
WEB | Admin panel changes
APP | Registration funnel UI
```

Set **Original Estimate**, **Assignee**, and sprint.

### Stage testing

Use QA titles with a platform:

```
QA | WEB | Events PRD — 1st iteration (stage testing)
QA | APP | Smoke on staging
QA | BE | API contract testing
```

Set **Original Estimate** and assign to the QA owner.

### Web and Mobile — Pre-Prod (QA) and UAT (Product + Design)

Create **separate tasks** for Pre-Prod and UAT. Stage is determined by **pipe segment 3** (QA) or **segment 2** (UAT) — not keywords elsewhere in the title.

| Phase | Web example | Mobile example |
|-------|-------------|----------------|
| Pre-Prod | `QA \| WEB \| Pre-Prod \| regression` | `QA \| APP \| Pre-Prod \| regression` |
| Pre-Prod (alt) | `QA \| WEB \| Prod testing \| smoke` | `QA \| APP \| Final Testing \| e2e` |
| UAT | `WEB \| UAT \| sign-off with product` | `APP \| UAT \| design review` |

QA never owns UAT. Do **not** use `QA \| WEB \| UAT …` for product UAT — that maps to **Stage testing**.

### Ready for release — status only (no task)

After UAT is done:

1. Close or complete the UAT task(s).  
2. Move the epic or stories to Jira status **Ready for Release**.

Do **not** create a task only to mark “ready for release” in the title.

### Backend — Prod release and Prod final testing

Create tasks when there is real work to do and estimate:

| Phase | Example summary |
|-------|-----------------|
| Prod release | `BE \| Prod release \| events API` |
| Prod final testing | `BE \| Prod final testing \| smoke` or `QA \| BE \| Final Testing \| API validation` |

Set **Original Estimate** and dates like other tasks.

**Backend is live** when the **Prod release** task is **closed** (or moved to Done). That is the go-live point for Backend — you do not wait for Prod final testing to finish before calling Backend live.

Prod final testing is follow-up validation after release; track it with its own task if your team does that work.

### Go live — no task

Do **not** create a separate `go live` task.

| Platform | Backend / Web / Mobile is live when |
|----------|-------------------------------------|
| **Backend** | **Prod release** task is **closed** |
| **Web / Mobile** | Epic or stories are in **Ready for Release** and the build is live in production |

### Bug fixes and stage final testing — no task by default

Teams usually do not create separate Jira tasks for these phases. If you do plan them as explicit work, create a normal task with a clear `BE |` / `WEB |` / `APP |` or `QA |` title and an estimate.

---

## Estimates and assignment

| Issue type | What to set in Jira |
|------------|-------------------|
| Task / Sub-task | **Original Estimate** before sprint planning |
| Bug (open) | Estimate optional |
| Bug (resolved) | **Time spent** on worklog |

Also:

- Break large work into multiple tasks under the right Story/Epic.  
- Always set **Assignee**.

---

## Bugs

1. Issue type **Bug**.  
2. Parent: Epic or Story under that Epic.  
3. In the sprint if the team tracks it this sprint.  
4. When fixed: log **Time spent**.  
5. Optional summary prefix: `WEB \| …`, `APP \| …`, `BE \| …`  
6. Status **Not a Bug**: no worklog needed.  
7. Open bugs (To Do, In Progress, Hold, Deferred): worklog not required until resolved.

---

## Leave log

Log leave and delays **only** as dedicated **leave** tasks. Do not put leave hours inside development or QA estimates.

### When to create a leave task

- Planned leave (PTO, holiday, offsite, etc.)  
- Unplanned delay on an epic (blocked, waiting on access, etc.)

Create a **Task** or **Sub-task** on the **same Epic**, assign to yourself, and add to the sprint.

### Hours and dates

| Field | Rule |
|-------|------|
| **Original Estimate** | **6 hours per leave day** (one day = `6h`) |
| **Start date** | First day of leave or delay |
| **Due date** | Last day of leave or delay |

| Leave | Start | Due | Original Estimate |
|-------|-------|-----|-------------------|
| 1 day | Wed 4 Jun | Wed 4 Jun | `6h` |
| 3 days (Mon–Wed) | Mon 2 Jun | Wed 4 Jun | `18h` |
| Half day | Fri 6 Jun | Fri 6 Jun | `3h` |

Count **working days** (Mon–Fri) only.

### Summary (required)

| Summary starts with | Meaning |
|---------------------|---------|
| `Leave \| Planned` | Planned leave |
| `Leave \| Unplanned` | Unplanned delay |
| `Leave \| {reason}` | Planned leave (e.g. `Leave \| Health Issue`) |

Examples:

```
Leave | Planned — Diwali PTO
Leave | Planned — Team offsite (2 days)
Leave | Unplanned — Waiting for prod access
Leave | Health Issue
```

Add a short reason after the prefix.

### Leave task checklist

| Field | Value |
|-------|--------|
| Summary | `Leave \| Planned`, `Leave \| Unplanned`, or `Leave \| {reason}` |
| Original Estimate | 6h × number of leave days |
| Start date | Leave start |
| Due date | Leave end |
| Assignee | Person on leave |
| Epic | Same epic as delivery work |
| Sprint | Active sprint |

No **BE** / **WEB** / **APP** prefix on leave tasks. Have at least one normal `BE |` / `WEB |` / `APP |` / `QA |` task on the same epic so leave ties to the right team.

### Leave — do not

- Mix leave hours into `BE |` or `QA | WEB |` task estimates  
- Use issue type **Bug** for leave  
- Omit the `Leave \|` prefix  

---

## Epic and sprint structure

1. One **Epic** per PRD/delivery.  
2. Add execution tasks, sub-tasks, and bugs to the **active sprint**.  
3. Parent chain: Task → Story → Epic (or Task → Epic if that is your process).  
4. Order epics on the board using Jira **Rank** (drag-and-drop).

---

## Sprint planning checklist

- [ ] Epic in the sprint  
- [ ] `BE \| Assessment`, `WEB \| Assessment`, `APP \| Assessment` where needed  
- [ ] Development: `BE \|`, `WEB \|`, or `APP \|` + Original Estimate + Assignee  
- [ ] Platform QA: `QA \| WEB \|`, `QA \| APP \|`, or `QA \| BE \|`  
- [ ] Separate Pre-Prod and UAT tasks on Web and Mobile  
- [ ] **Ready for Release** status after UAT — no ready-for-release task  
- [ ] Backend live when **Prod release** is closed; Web/Mobile: **Ready for Release** — no go-live task  
- [ ] Bugs: type Bug, worklog when fixed  
- [ ] Leave: `Leave \| …`, 6h per day, Start and Due dates  

---

## Common mistakes

| Mistake | What to do instead |
|---------|-------------------|
| No `\|` in summary | Add `BE \|`, `WEB \|`, `APP \|`, `QA \|`, or `Leave \|` |
| Wrong first prefix (`Backend`, `Stage-APP`, etc.) | Use **BE**, **WEB**, or **APP** only |
| `QA \| …` without WEB / APP / BE for platform work | Add `QA \| WEB \|`, `QA \| APP \|`, or `QA \| BE \|` |
| Feature work as Bug | Use Task / Sub-task |
| Task with no Original Estimate | Add estimate before planning |
| One task for “UAT + Pre-prod” | Split into two tasks |
| Task only for “ready for release” | Use status **Ready for Release** |
| Task only for “go live” | Backend: close **Prod release**; Web/Mobile: use status; no go-live ticket |
| Leave inside dev/QA estimate | Separate `Leave \| …` task |
| Leave without 6h/day or dates | 6h per day + Start + Due |

---

## Questions

Copy a similar ticket that already follows this doc, or ask your EM before creating many issues at once.
