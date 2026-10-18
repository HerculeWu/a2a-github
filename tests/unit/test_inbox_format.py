from a2a.inbox import format_lines


def entry(number, type_, author, ts, snippet, repo="lab/paper"):
    e = {"id": f"x-{number}", "number": number, "type": type_, "author": author, "ts": ts, "snippet": snippet}
    if repo is not None:
        e["repo"] = repo
    return e


def test_golden_single_line_matches_spec_example():
    lines = format_lines([entry(123, "comment", "alice", "2026-10-17T17:40:12Z", "能不能改成…")])
    assert lines == ["lab/paper#123  comment   alice  2026-10-17T17:40  能不能改成…"]


def test_golden_lines_across_repos_pad_to_the_widest_thread():
    lines = format_lines(
        [
            entry(123, "comment", "alice", "2026-10-17T17:40:00Z", "能不能改成…"),
            entry(7, "assigned", "bob", "2026-10-17T17:42:00Z", "assignee: agent-x", repo="lab/sim"),
        ]
    )
    assert lines == [
        "lab/paper#123  comment   alice  2026-10-17T17:40  能不能改成…",
        "lab/sim#7      assigned  bob    2026-10-17T17:42  assignee: agent-x",
    ]


def test_golden_alignment_across_rows():
    lines = format_lines(
        [
            entry(7, "comment", "alice", "2026-10-17T17:40:00Z", "short"),
            entry(1234, "review_requested", "bob-the-builder", "2026-10-17T18:05:00Z", "reviewer: me-bot"),
            entry(42, "labeled", "me-bot", "2026-10-17T18:06:00Z", ""),
        ]
    )
    assert lines == [
        "lab/paper#7     comment           alice            2026-10-17T17:40  short",
        "lab/paper#1234  review_requested  bob-the-builder  2026-10-17T18:05  reviewer: me-bot",
        "lab/paper#42    labeled           me-bot           2026-10-17T18:06",
    ]


def test_an_entry_without_repo_shows_a_bare_number():
    lines = format_lines(
        [
            entry(5, "comment", "alice", "2026-10-17T17:40:00Z", "old", repo=None),
            entry(7, "comment", "bob", "2026-10-17T17:41:00Z", "new", repo="lab/sim"),
        ]
    )
    assert lines == [
        "#5         comment   alice  2026-10-17T17:40  old",
        "lab/sim#7  comment   bob    2026-10-17T17:41  new",
    ]


def test_snippet_cut_to_60_display_columns():
    (line,) = format_lines([entry(1, "comment", "a", "2026-10-17T00:00:00Z", "字" * 50)])
    shown = line.split("  ")[-1]
    assert shown == "字" * 29 + "…"


def test_empty():
    assert format_lines([]) == []
