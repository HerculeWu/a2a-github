from a2a.inbox import format_lines


def entry(number, type_, author, ts, snippet):
    return {"id": f"x-{number}", "number": number, "type": type_, "author": author, "ts": ts, "snippet": snippet}


def test_golden_single_line_matches_spec_example():
    lines = format_lines([entry(123, "comment", "alice", "2026-10-17T17:40:12Z", "能不能改成…")])
    assert lines == ["#123  comment   alice  2026-10-17T17:40  能不能改成…"]


def test_golden_alignment_across_rows():
    lines = format_lines(
        [
            entry(7, "comment", "alice", "2026-10-17T17:40:00Z", "short"),
            entry(1234, "review_requested", "bob-the-builder", "2026-10-17T18:05:00Z", "reviewer: me-bot"),
            entry(42, "labeled", "me-bot", "2026-10-17T18:06:00Z", ""),
        ]
    )
    assert lines == [
        "#7     comment           alice            2026-10-17T17:40  short",
        "#1234  review_requested  bob-the-builder  2026-10-17T18:05  reviewer: me-bot",
        "#42    labeled           me-bot           2026-10-17T18:06",
    ]


def test_snippet_cut_to_60_display_columns():
    (line,) = format_lines([entry(1, "comment", "a", "2026-10-17T00:00:00Z", "字" * 50)])
    shown = line.split("  ")[-1]
    assert shown == "字" * 29 + "…"


def test_empty():
    assert format_lines([]) == []
