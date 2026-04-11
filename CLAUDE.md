## Working style (always follow these)

- **Ask questions over assuming** — always prefer clarifying questions before making decisions
- **No code until the plan is solid** — currently in architecture/schema design phase (discovery complete)
- **Log everything** — user queries → `planning/input.md`, assistant responses → `planning/output.md`
- **Timestamps on every log entry** — run `date '+%Y-%m-%d %H:%M:%S'` first, format: `YYYY-MM-DD HH:MM:SS`
- **Learn from mistakes** — when a miss or gap is found, log it in `planning/lessons.md` with root cause + fix, then update all affected docs. Read `planning/lessons.md` at the start of every session.
- **Propagate discoveries immediately** — when analysis reveals new facts, update CLAUDE.md and PRD before moving on
- **Close open questions** — when a decision is made, mark the corresponding open question ✅ in the PRD
- **PRD → tasks.md sync** — every new "must implement" requirement in the PRD documents (in /planning/PRD) needs a corresponding task in tasks.md

---

## Workflow principles (always follow these)

### Plan before acting
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions) — write the plan, get sign-off, then execute
- If something goes sideways mid-task: STOP and re-plan. Don't keep pushing.
- Write detailed specs upfront to reduce ambiguity

### Subagent strategy
- Use subagents liberally to keep the main context window clean
- Offload research, exploration, and parallel analysis to subagents
- One focused task per subagent — don't give a subagent multiple unrelated jobs

### Verification before done
- Never mark a task complete without proving it works (tests pass, behaviour confirmed)
- Ask: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness — don't self-certify without evidence

### Demand elegance
- For non-trivial changes: pause and ask "is there a more elegant solution?"
- If a fix feels hacky: implement the proper solution instead
- Skip this for simple, obvious fixes — don't over-engineer

### Autonomous bug fixing
- When given a bug report: diagnose and fix it. Don't ask for hand-holding.
- Point at logs, errors, failing tests — then resolve them
- Go fix failing tests without being told how

### Autonomous PRD, tasks and schema updating
- When in the context of a prompt user suggest a new feature, add that feature to the right PRD file in /planning/PRD, idnetifying the right place in the prd and if necessary, modify other features to connect them to the new feature
- If a new feature impact the schema, also modify the schema.md file
- The objective is to maintain all the files in /planning/PRD and schema.md as evergreen, always updated documents

### Core quality principles
- **Simplicity first** — make every change as simple as possible, touch minimal code
- **No laziness** — find root causes, no temporary fixes, senior developer standards
- **Minimal impact** — changes should only touch what's necessary, avoid introducing bugs

### Generality principles (always follow these)
- **When building features, never build for a specific instance, model, or OS.** Features must work across all instances, all models (LLM providers + Suno/Udio/MusicGen, Spotify/Apple/TikTok, etc), all operating systems. If a feature has a "default value" that's instance-specific, it's a bug waiting to happen.
- **When fixing issues, never hardcode a solution specific to the test use case, instance, model, or OS.** If a bug report says "Drake's audio features are wrong", the fix is never "special-case Drake" — it's to find the class of inputs that trigger the bug and make it work for all of them. If the fix involves the string "Drake" or the ID `1932`, you've done it wrong.
- **Think systemically.** Hyper-generalized features work in any combination of variables. Hyper-generalized fixes work on any instance that matches the class of problem. Parameterize the variables that change. Treat every hardcoded constant that references a specific real-world entity (artist name, track ID, platform name in a comparison, file path, hostname, country code, genre label, OS, CPU arch) as a code smell that needs justification.
- **The only acceptable hardcoded values** are: (1) the canonical source-of-truth config files (`config/*.json`, `shared/constants.py`, `shared/genre_taxonomy.py`), (2) API endpoint paths that are part of the external API contract, (3) test fixtures in `tests/`, and (4) short-lived diagnostic probes clearly flagged as such in the code.

---

## LLM usage principle (always follow these)

- **Every LLM call must be logged** — model, input tokens, output tokens, estimated cost, timestamp, action type. No exceptions.

---

## Testing strategy (always follow these)

- **TDD** — write the failing test first, then write the minimum code to make it pass. **Every plan must lead with tests — never list tests only as a verification step at the end.** If TDD proves too slow for a specific area, flag it and agree a change before deviating.
- **Backend**: `xUnit` as the test framework. `Moq` for mocking. `WebApplicationFactory` for integration tests (full request pipeline against a real test DB).
- **Frontend**: `Vitest` + `React Testing Library` for component-level unit tests.
- **E2E**: `Playwright` — planned for v1.1, not MVP.
- Every feature ships with tests. No feature is considered done until its tests pass.

---

## Task tracking & agent coordination

All tasks live in `planning/tasks.md`. This is the single source of truth for what is done, in progress, and upcoming.

**Protocol (all agents must follow):**
1. Before starting any task → claim it: set `status` to `in_progress`, write your identifier to `assigned_to`
2. Do not start a task whose `depends_on` list contains any non-`done` task
3. On completion → set `status` to `done`, clear `assigned_to`
4. Only the orchestrator (main Claude session) creates, removes, or rescopes tasks

Tasks are coarse-grained (feature-level) for now. Break into sub-tasks only if parallelising sub-agents.

---

## README maintenance

`README.md` is the first thing seen when returning to the repo after a long gap. Keep it in sync.

**Update README when:**
- A phase changes status (starts or completes)
- A tech stack decision is locked in or changed
- Deployment target changes
- Major MVP scope changes (features added or removed)

See L008 in `planning/lessons.md`.

---

## Planning artifacts

| File | Purpose |
|---|---|
| `planning/lessons.md` | Mistakes and misses log — read at start of every session |
| `planning/schema.md` | Approved database schema — feeds T004 migrations |
| `planning/tasks.md` | Master task list — canonical backlog and progress tracker |
| `planning/PRD/[varoius .md files]` | Living PRD with full feature detail |
| `planning/input.md` | All user messages, timestamped |
| `planning/output.md` | All assistant responses, timestamped |
| `planning/competitor_features.md` | Feature comparison from competitors |