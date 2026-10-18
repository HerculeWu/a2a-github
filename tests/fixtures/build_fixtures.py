"""Regenerate the recorded-GitHub-response fixtures for watch tests.

Run: python tests/fixtures/build_fixtures.py
Scenario A is a busy morning in org/repo as seen by me-bot; B is A plus later activity.
Scenario multi is A plus a second repository, org/sim, whose activity interleaves with A's.
"""

import json
from pathlib import Path
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
REPO = "org/repo"
GH = "https://github.com/org/repo"
API = f"https://api.github.com/repos/{REPO}"
D = "2026-10-17T"


def user(login):
    return {"login": login}


def gh_url(repo):
    return f"https://github.com/{repo}"


def api_url(repo):
    return f"https://api.github.com/repos/{repo}"


def issue(number, title, login, created, updated, body="", labels=(), assignees=(), pr=False, repo=REPO, iid=None):
    item = {
        "id": iid or 1000 + number,
        "number": number,
        "title": title,
        "user": user(login),
        "body": body,
        "labels": [{"name": n} for n in labels],
        "assignees": [user(a) for a in assignees],
        "state": "open",
        "created_at": created,
        "updated_at": updated,
        "html_url": f"{gh_url(repo)}/{'pull' if pr else 'issues'}/{number}",
    }
    if pr:
        item["pull_request"] = {"url": f"{api_url(repo)}/pulls/{number}"}
    return item


def comment(cid, number, login, created, body, updated=None, repo=REPO):
    return {
        "id": cid,
        "user": user(login),
        "body": body,
        "created_at": created,
        "updated_at": updated or created,
        "issue_url": f"{api_url(repo)}/issues/{number}",
        "html_url": f"{gh_url(repo)}/issues/{number}#issuecomment-{cid}",
    }


def event(eid, kind, issue_item, actor, created, **extra):
    return {"id": eid, "event": kind, "actor": user(actor), "created_at": created, "issue": issue_item, **extra}


def review(rid, number, login, submitted, body, state="COMMENTED"):
    return {
        "id": rid,
        "user": user(login),
        "body": body,
        "state": state,
        "submitted_at": submitted,
        "html_url": f"{GH}/pull/{number}#pullrequestreview-{rid}",
    }


def review_comment(cid, number, review_id, login, created, path, body):
    return {
        "id": cid,
        "pull_request_review_id": review_id,
        "user": user(login),
        "body": body,
        "path": path,
        "line": 10,
        "created_at": created,
        "updated_at": created,
        "pull_request_url": f"{API}/pulls/{number}",
        "html_url": f"{GH}/pull/{number}#discussion_r{cid}",
    }


def search_path(q):
    return "search/issues?" + urlencode({"q": q, "per_page": 100})


def streams(repo):
    return {
        "issues": f"repos/{repo}/issues?state=all&sort=updated&direction=desc&per_page=100",
        "comments": f"repos/{repo}/issues/comments?sort=updated&direction=desc&per_page=100",
        "review_comments": f"repos/{repo}/pulls/comments?sort=updated&direction=desc&per_page=100",
        "events": f"repos/{repo}/issues/events?per_page=100",
    }


STREAM = streams(REPO)
ISSUES_PAGE2 = "repositories/1/issues?state=all&sort=updated&direction=desc&per_page=100&page=2"

# --- scenario A -------------------------------------------------------------
i1 = issue(1, "Docs typo", "carol", D + "10:00:00Z", D + "10:30:00Z", body="typo in README")
i2 = issue(2, "Crash on empty config", "alice", D + "10:10:00Z", D + "10:40:00Z",
           body="Steps to reproduce:\n1. empty config\n2. boom", labels=["bug"], assignees=["me-bot"])
i3 = issue(3, "Add retry to fetcher", "bob", D + "10:20:00Z", D + "10:50:00Z",
           body="Implements retries.\n\ncc @me-bot", pr=True)

comments_a = [
    comment(103, 1, "carol", D + "10:30:00Z", "Thanks for the reply!"),
    comment(102, 2, "alice", D + "10:15:00Z", "Any update on this?"),
    comment(101, 1, "me-bot", D + "10:05:00Z", "I'll look into it."),
    comment(100, 1, "carol", "2026-10-16T09:00:00Z", "old comment, edited today", updated=D + "10:02:00Z"),
]
events_a = [
    event(503, "subscribed", i2, "alice", D + "10:13:00Z"),
    event(501, "assigned", i2, "alice", D + "10:12:00Z", assignee=user("me-bot")),
    event(502, "labeled", i2, "alice", D + "10:11:00Z", label={"name": "bug"}),
]
reviews3_a = [review(701, 3, "dan", D + "10:50:00Z", "LGTM @me-bot")]

A = {
    STREAM["issues"]: {"etag": 'W/"a-issues"', "body": [i3, i2], "next": ISSUES_PAGE2, "headers": {"X-Poll-Interval": "60"}},
    ISSUES_PAGE2: {"body": [i1]},
    STREAM["comments"]: {"etag": 'W/"a-comments"', "body": comments_a},
    STREAM["review_comments"]: {"etag": 'W/"a-rc"', "body": []},
    STREAM["events"]: {"etag": 'W/"a-events"', "body": events_a},
    f"repos/{REPO}/pulls/3/reviews?per_page=100": {"body": reviews3_a},
    search_path(f"repo:{REPO} author:me-bot"): {"body": {"items": []}},
    search_path(f"repo:{REPO} commenter:me-bot"): {"body": {"items": [{"number": 9}]}},
    search_path(f"repo:{REPO} reviewed-by:me-bot"): {"body": {"items": []}},
}

# --- scenario B = A + later activity ----------------------------------------
i9 = issue(9, "Old discussion", "frank", "2026-09-01T08:00:00Z", D + "11:30:00Z", body="let's talk")
i4 = issue(4, "Please pin me", "erin", D + "11:10:00Z", D + "11:10:00Z", body="needs an agent", labels=["pin:me-bot"])
i3b = {**i3, "updated_at": D + "11:40:00Z"}

B = json.loads(json.dumps(A))
B[STREAM["issues"]] = {"etag": 'W/"b-issues"', "body": [i3b, i9, i4, i2], "next": ISSUES_PAGE2, "headers": {"X-Poll-Interval": "120"}}
B[STREAM["comments"]] = {"etag": 'W/"b-comments"', "body": [comment(104, 9, "erin", D + "11:30:00Z", "Reviving this thread.")] + comments_a}
B[STREAM["review_comments"]] = {
    "etag": 'W/"b-rc"',
    "body": [review_comment(801, 3, 702, "dan", D + "11:40:00Z", "fetch.py", "nit: rename, @me-bot thoughts?")],
}
B[STREAM["events"]] = {"etag": 'W/"b-events"', "body": [event(504, "labeled", i4, "erin", D + "11:10:00Z", label={"name": "pin:me-bot"})] + events_a}
B[f"repos/{REPO}/pulls/3/reviews?per_page=100"] = {"body": reviews3_a + [review(702, 3, "dan", D + "11:40:00Z", "")]}
B[f"repos/{REPO}/issues/9"] = {"body": i9}


# --- scenario multi = A + org/sim --------------------------------------------
SIM = "org/sim"
SIM_STREAM = streams(SIM)
s1 = issue(1, "Sim run diverges", "gina", D + "10:25:00Z", D + "10:40:00Z", body="diverges after step 40",
           repo=SIM, iid=2001)
MULTI = json.loads(json.dumps(A))
MULTI.update({
    SIM_STREAM["issues"]: {"etag": 'W/"sim-issues"', "body": [s1], "headers": {"X-Poll-Interval": "90"}},
    SIM_STREAM["comments"]: {"etag": 'W/"sim-comments"', "body": [
        # sim#1 is not a Participated Thread, though org/repo#1 is
        comment(3002, 1, "gina", D + "10:40:00Z", "never mind, found it", repo=SIM),
        comment(3001, 1, "gina", D + "10:35:00Z", "@me-bot can you check the seed?", repo=SIM),
    ]},
    SIM_STREAM["review_comments"]: {"etag": 'W/"sim-rc"', "body": []},
    SIM_STREAM["events"]: {"etag": 'W/"sim-events"', "body": []},
    f"repos/{SIM}/issues/1": {"body": s1},
    search_path(f"repo:{SIM} author:me-bot"): {"body": {"items": [{"number": 5}]}},
    search_path(f"repo:{SIM} commenter:me-bot"): {"body": {"items": []}},
    search_path(f"repo:{SIM} reviewed-by:me-bot"): {"body": {"items": []}},
})

# --- fetch scenario -----------------------------------------------------------
SIGN = "\n\n<sub>— agent-x</sub>\n<!-- a2a:from=agent-x -->"
FETCH = {
    f"repos/{REPO}/issues/2": {"body": {**i2, "body": "Steps to reproduce:\n1. empty config\n2. boom"}},
    f"repos/{REPO}/issues/2/comments?per_page=100": {
        "body": [
            comment(201, 2, "alice", D + "10:15:00Z", "Any update on this?"),
            comment(202, 2, "me-bot", D + "10:20:00Z", "On it." + SIGN),
        ],
        "next": "repositories/1/issues/2/comments?per_page=100&page=2",
    },
    "repositories/1/issues/2/comments?per_page=100&page=2": {
        "body": [comment(203, 2, "alice", D + "11:00:00Z", "Thanks!")]
    },
    f"repos/{REPO}/issues/3": {"body": i3},
    f"repos/{REPO}/issues/3/comments?per_page=100": {"body": [comment(301, 3, "carol", D + "10:30:00Z", "Nice.")]},
    f"repos/{REPO}/pulls/3": {
        "body": {
            **{k: i3[k] for k in ("id", "number", "title", "user", "body", "labels", "assignees", "state", "created_at", "html_url")},
            "draft": False,
            "merged": False,
            "base": {"ref": "main"},
            "head": {"ref": "retry"},
            "additions": 30,
            "deletions": 4,
            "changed_files": 2,
        }
    },
    f"repos/{REPO}/pulls/3/reviews?per_page=100": {
        "body": [
            review(701, 3, "dan", D + "10:50:00Z", "LGTM @me-bot", state="APPROVED"),
            review(702, 3, "dan", D + "11:40:00Z", ""),
            {**review(703, 3, "dan", None, "draft"), "state": "PENDING"},
        ]
    },
    f"repos/{REPO}/pulls/3/comments?per_page=100": {
        "body": [review_comment(801, 3, 702, "dan", D + "11:40:00Z", "fetch.py", "nit: rename")]
    },
    # a Thread in a repository the fetching Workspace need not observe
    "repos/lab/sim/issues/7": {"body": issue(7, "Sim run diverges", "gina", D + "09:00:00Z", D + "09:00:00Z",
                                             body="diverges after step 40", repo="lab/sim", iid=2007)},
    "repos/lab/sim/issues/7/comments?per_page=100": {"body": []},
    f"repos/{REPO}/pulls/3/files?per_page=100": {
        "body": [
            {"filename": "a2a/fetch.py", "status": "modified", "additions": 26, "deletions": 4},
            {"filename": "tests/test_retry.py", "status": "added", "additions": 4, "deletions": 0},
        ]
    },
}
DIFF = (
    "diff --git a/a2a/fetch.py b/a2a/fetch.py\n--- a/a2a/fetch.py\n+++ b/a2a/fetch.py\n@@ -1 +1 @@\n-old\n+new\n"
    "diff --git a/tests/test_retry.py b/tests/test_retry.py\nnew file mode 100644\n--- /dev/null\n"
    "+++ b/tests/test_retry.py\n@@ -0,0 +1 @@\n+def test(): pass\n"
)


def write(name, routes, commands=None):
    d = HERE / name
    d.mkdir(exist_ok=True)
    (d / "routes.json").write_text(json.dumps(routes, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if commands:
        (d / "commands.json").write_text(json.dumps(commands, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write("watch_a", A)
    write("watch_b", B)
    write("watch_multi", MULTI)
    write("fetch", FETCH, {f"pr diff 3 --repo {REPO}": DIFF})
