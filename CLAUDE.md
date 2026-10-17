# a2a-github

Role-agnostic CLI primitives that let humans and agents collaborate through one GitHub repository.

- **Vocabulary**: [CONTEXT.md](CONTEXT.md). Use its terms in code, tests, and docs. When a term changes or a new one settles, update it there.
- **Design**: [docs/design.md](docs/design.md) is the authoritative spec. Read it before changing behaviour. [docs/spec.md](docs/spec.md) is the original request, kept for intent.
- **Decisions**: [docs/adr/](docs/adr/). Read the relevant ADR before reversing anything that looks odd. Record new hard-to-reverse trade-offs as the next numbered ADR.

## Working rules

- Runtime code in `a2a/` imports only the standard library (ADR-0003). Every `gh` invocation goes through `GhClient` (ADR-0002).
- Build test-first, one primitive per vertical slice and commit, in the order given in design.md's "Build order".
- Run tests with `.venv/bin/pytest --cov=a2a`. Coverage must stay ≥ 85%.
- Write everything agents or CLI users see (SKILL.md, CLI output, help text, CONTEXT.md, ADRs) in English. Only README.md is bilingual (zh/en).
- `a2a/` stays free of agent-specific integration (ADR-0001). Claude Code packaging lives in `bin/`, `skills/`, and `.claude-plugin/`.
