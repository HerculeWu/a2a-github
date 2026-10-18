# What GitHub can carry a link between a Linked and a Home Repository

Research for [#4](https://github.com/HerculeWu/a2a-github/issues/4), under the map [#1](https://github.com/HerculeWu/a2a-github/issues/1). This file states facts and makes no design decision.

Sources are docs.github.com (fetched 2026-10-18 as Markdown through `https://docs.github.com/api/article/body?pathname=…`), the `cli/cli` source, and read-only `gh api` probes (gh 2.45.0) against `cli/cli` (an organization repository, where the probing Login has only public read access) and `HerculeWu/a2a-github` (a personal repository, where the Login is the owner). Nothing was written to any repository.

## Background facts that apply to every carrier

- **Personal-account repositories have only two levels: the owner and collaborators.** Every collaborator can push. *"Collaborators can't have read-only access to repositories owned by a personal account."* There is no triage, maintain or admin role, so an action that needs Maintain or Admin in an organization can be done only by the owner in a personal repository. ([Permission levels for a personal account repository](https://docs.github.com/en/account-and-profile/reference/permission-levels-for-a-personal-account-repository))
- **Organization repositories have five roles: Read, Triage, Write, Maintain and Admin.** The rows quoted below come from the role table. ([Repository roles for an organization](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization))
- **a2a polls four endpoints:** `issues`, `issues/comments`, `pulls/comments` and `issues/events`, all REST with ETags, and GraphQL is excluded because it is POST-only and gets no 304 (ADR-0004). `issues/events` reports only events on an issue or a PR. Changes to repository settings or metadata are not issue events. ([Issue event types](https://docs.github.com/en/rest/using-the-rest-api/issue-event-types))
- **Owner and repository names are case-insensitive in the REST API** (*"The name is not case sensitive"*, on every REST path parameter). Repository names can contain `.` and `_`, for example `vercel/next.js`.

## Comparison

"Write" means setting or changing the carrier, and "Read" means reading its value. Org roles are R/T/W/M/A.

| Carrier | Who can write (org) | Who can write (personal) | Who can read | Org only? | gh read / write | Atomic create usable as a claim? | Activity in a2a's polled endpoints? |
|---|---|---|---|---|---|---|---|
| **Repository topics** | Maintain, Admin | owner only | anyone who can read the repository (public: anyone) | no | `gh repo view --json repositoryTopics` or `gh api repos/O/R/topics`; `gh repo edit --add-topic X` | **no**: `PUT /topics` replaces the whole list, and `gh repo edit --add-topic` does a read-modify-write | **no** |
| **Custom properties** | org admins define them; values are set by repository Admin or by a holder of the "edit custom property values" fine-grained permission, and through the UI only when the property allows "repository actors" to set it | **not available** (a personal repository returns 404) | anyone who can read the repository (public: anyone) | **yes** | `gh api repos/O/R/properties/values` (also `custom_properties` in `GET repos/O/R`); write: `gh api -X PATCH …/properties/values`. There is no gh subcommand | **no**: the PATCH is "create or update" | **no** |
| **Description / homepage** | Maintain, Admin ("Edit a repository's description") | owner (not in the collaborator list; inferred) | anyone who can read the repository | no | `gh repo view --json description,homepageUrl`; `gh repo edit -d … -h …` | **no**: PATCH, last writer wins | **no** |
| **Label (repository level)** | create, edit or delete: Write, Maintain, Admin. Applying one: Triage and up | any collaborator | anyone who can read the repository | no | `gh label list`, `gh api repos/O/R/labels/NAME`; `gh label create` | **yes**: a duplicate name gets `422 already_exists`; this is what ADR-0008 uses. Name lookup is case-insensitive | creating the label: **no**. Applying it to an issue: **yes**, `labeled` |
| **Issue with a fixed label** (like the Protocol Thread) | opening: Read and up (anyone, on a public repository). Labeling: Triage and up; on create, labels are *"silently dropped"* without push access | opening: anyone on a public repository, collaborators on a private one; labeling: collaborators | anyone who can read the repository | no | `gh issue list --label L`; `gh issue create --label L` | the issue: **no**. Claim through the label create, as in ADR-0008 | **yes**: `issue_opened`, `labeled`, `comment`. Body edits are not Activity |
| **Pinned issue** | the current docs do not say who; older docs: *"People with write access to a repository can pin issue"* | collaborators (write) | anyone who can read the repository | no | read: **GraphQL only** (`repository.pinnedIssues`); the REST issue object has no pinned flag. Write: `gh issue pin N` | **no**. At most 3 pinned issues per repository | `pinned` and `unpinned` **appear in `issues/events`**; a2a currently ignores them |
| **Repository variable** (Actions) | Write, Maintain, Admin | any collaborator | **collaborators only**: a non-collaborator on a public repository gets 403 | no | `gh variable list`, `gh api repos/O/R/actions/variables/NAME` (gh 2.45 has no `gh variable get`); write: `gh api -X POST repos/O/R/actions/variables` | **yes, through a raw POST**: the server returns 409 when the name exists, as the `cli/cli` source records. `gh variable set` is **not** a claim: on 409 it falls back to PATCH | **no** |

## Per-carrier details and sources

### Repository topics

- *"Repository admins can add any topics they'd like."* The org role table lists "Manage topics" for Maintain and Admin. The personal-repository owner table lists "Manage the repository's topics" as owner-only. ([Classifying your repository with topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics), [org roles](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization), [personal levels](https://docs.github.com/en/account-and-profile/reference/permission-levels-for-a-personal-account-repository))
- Format: *"lowercase letters, numbers, and hyphens … 50 characters or less … no more than 20 topics"*, and *"Topic names will be saved as lowercase"*. *"Topic names are always public, even if you create the topic from within a private repository."* A topic therefore cannot carry an arbitrary `owner/repo`, which needs `/` and may need `.` or `_`.
- REST: `GET /repos/{o}/{r}/topics` needs fine-grained "Metadata: read". `PUT /repos/{o}/{r}/topics` needs "Administration: write" and replaces all topics. ([Repos REST](https://docs.github.com/en/rest/repos/repos), [fine-grained PAT permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens))
- Topics are searchable (`topic:` qualifier), and private repositories appear only to users who can access them.
- `gh repo edit --add-topic` fetches the current topics, adds to that set and PUTs the whole list (`cli/cli` `pkg/cmd/repo/edit/edit.go`). Two concurrent adds can therefore lose one.
- Probe: `GET repos/cli/cli/topics` returned 200 with the topic names for a public non-collaborator.

### Custom properties

- They are defined at the organization (or enterprise) level: *"You can add custom properties to your organization and set values for those properties for repositories in your organization."* The org REST endpoints for definitions require *"An administrator for the organization"* or a holder of `custom_properties_org_definitions_manager`. ([Managing custom properties](https://docs.github.com/en/organizations/managing-organization-settings/managing-custom-properties-for-repositories-in-your-organization), [Org custom properties REST](https://docs.github.com/en/rest/orgs/custom-properties))
- Repository values: `PATCH /repos/{o}/{r}/properties/values` is open to *"Repository admins and other users with the repository-level 'edit custom property values' fine-grained permission"* (fine-grained PAT "Custom properties: write"). A null value unsets a property. In the UI, a property can opt into *"Allow repository actors to set this property"*. The org role table lists "Edit the custom property values for the repository" for **Admin only**. ([Repo custom properties REST](https://docs.github.com/en/rest/repos/custom-properties))
- Read: `GET /repos/{o}/{r}/properties/values`: *"Users with read access to the repository can use this endpoint"* (fine-grained "Metadata: read"). *"Custom properties on public repositories can be viewed by anyone."*
- Format: the type is a string, single select, multi select or boolean. Values may contain *"All printable ASCII characters except `"`"* and are capped at 75 characters in the UI, so a long `owner/repo` may not fit.
- Probes: `GET repos/HerculeWu/a2a-github/properties/values` returned **404** (a personal repository), and `GET repos/HerculeWu/a2a-github` has `"custom_properties": null`. On `cli/cli` the same calls returned 200 `[]` and `{}`.

### Description and homepage

- The org role table lists "Edit a repository's description" for **Maintain and Admin**. The personal collaborator list does not include it, so it is owner-only there (inferred, not probed). REST `PATCH /repos/{o}/{r}` needs "Administration: write". ([org roles](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization), [fine-grained PAT permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens))
- Both are free text (`homepage` is a single URI) and are returned by `GET /repos/{o}/{r}` to anyone who can read the repository. They are a single shared slot that people also use for human-facing text, and a write has no conditional form.

### Labels

- *"Anyone with write access to a repository can create a label"* (editing and deleting need the same), and *"Anyone with triage access … can apply and dismiss labels."* In a personal repository, collaborators *"Manage labels"*. ([Managing labels](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels))
- `POST /repos/{o}/{r}/labels` returns 201 or 422. gh treats `422` with `errors[0].field == "name"` and `code == "already_exists"` as "label exists" (`cli/cli` `pkg/cmd/label/create.go`). This is the atomic claim ADR-0008 uses. Label lookup is case-insensitive (`GET repos/cli/cli/labels/BUG` returns `bug`). The label description is limited to *"100 characters or fewer"*. ([Labels REST](https://docs.github.com/en/rest/issues/labels))
- Creating or editing a repository label produces no issue event. Only applying a label to an issue or a PR yields `labeled` in `issues/events`.

### An issue with a fixed label

- Opening an issue needs Read, so on a public repository anyone who is signed in can open one. On create, *"Only users with push access can set labels for new issues. Labels are silently dropped otherwise."* Editing an issue body is open to *"Issue owners and users with push access or Triage role"*. ([Issues REST](https://docs.github.com/en/rest/issues/issues))
- Discovery: design.md's Team section uses `gh issue list --label a2a:protocol --state open`, and REST offers `GET /repos/{o}/{r}/issues?labels=…`. Neither is a claim, because a list query can miss an issue created a moment ago (ADR-0008), so the claim stays the label create.
- Activity: opening it is `issue_opened`, applying the label is `labeled`, and comments are `comment`. Body edits are not Activity (ADR-0006).

### Pinned issue

- *"You can pin up to three important issues above the issues list in your repository."* The current page states no role. The archived GHES 3.6 page states *"People with write access to a repository can pin issue in the repository."* ([Pinning an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/administering-issues/pinning-an-issue-to-your-repository), [GHES 3.6 archive](https://docs.github.com/en/enterprise-server@3.6/issues/tracking-your-work-with-issues/pinning-an-issue-to-your-repository))
- The API is GraphQL only: there are `pinIssue` and `unpinIssue` mutations, and `Repository.pinnedIssues` / `Issue.isPinned` (both checked by introspection). The REST issue object has no pinned field, which was checked on `cli/cli#13118`, a pinned issue. `gh issue pin` exists, but gh 2.45 `--json` exposes no `isPinned`.
- `pinned` and `unpinned` are issue events on the issue-events REST API. They are verified in `repos/cli/cli/issues/13118/events` (`"event":"pinned"`). a2a's events stream currently ignores every type outside its list.
- Related and newer: an issue can have one **pinned comment**: `PUT/DELETE /repos/{o}/{r}/issues/comments/{id}/pin` ("Issues: write"), and the REST issue object carries `pinned_comment`.

### Repository variables (GitHub Actions configuration variables)

- Docs: *"Authenticated users must have collaborator access to a repository to create, update, or read variables"*. Classic tokens need `repo` scope, and fine-grained PATs need "Variables: read/write". The org role table lists create, update and delete for **Write, Maintain and Admin**. ([Variables REST](https://docs.github.com/en/rest/actions/variables), [org roles](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization))
- Probe: `GET repos/cli/cli/actions/variables` as a public non-collaborator returned **403** *"You must have repository read permissions or have the repository variables fine-grained permission."* The owner of `HerculeWu/a2a-github` got 200. Being able to read a public repository is therefore not enough: a collaborator role is required.
- Create: `POST /repos/{o}/{r}/actions/variables` returns 201. The docs list no conflict code, but `cli/cli` `pkg/cmd/variable/set/http.go` says *"Server will return a 409 if variable already exists"* and falls back to PATCH. So a raw POST is a unique-name create, while `gh variable set` is an upsert. This was not probed, because probing it would mean writing.
- Names: *"alphanumeric characters … or underscores"*, not starting with `GITHUB_`, case-insensitive, *"unique to the repository"*. Limits: 48 KB per variable and 500 per repository. ([Variables reference](https://docs.github.com/en/actions/reference/workflows-and-actions/variables))

## Observations relevant to the linking question (facts, not decisions)

- **Only two carriers have an atomic create that fails on a duplicate: a label (422) and a repository variable (409 on a raw POST).** Both need Write in an organization repository, or collaborator status in a personal one.
- **Only the issue-based carriers produce Activity that a2a already turns into Inbox Entries** (`issue_opened`, `labeled`, `comment`). A pin produces a `pinned` issue event that a2a currently drops. Topics, custom properties, description, homepage, label creation and variables produce nothing on the polled endpoints, so a Participant would learn of them only by reading them.
- **Custom properties do not exist for personal repositories**, and for organization repositories their values need repository Admin, which in the UI also needs the org to opt the property in. They cannot serve the cross-owner case that #1 allows when either side is a personal account.
- **Topics cannot encode `owner/repo` losslessly**: they allow only lowercase letters, digits and hyphens, at most 50 characters, and they are always public.
- **Repository variables are invisible to non-collaborators even on public repositories.** In the organization case a read-only Participant can read them, and in the personal case every Participant with access is a collaborator.
- **In a personal repository every Participant with access can push.** Anything that needs only Write (labels, variables, pinning) is open to every collaborator, while topics, description and homepage stay owner-only.
- **Pinned issues are readable only through GraphQL**, which ADR-0004 rules out for polling.
