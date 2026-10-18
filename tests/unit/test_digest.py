from a2a.notify import digest, has_unannounced


def e(i, number, type_, author="x", repo="lab/paper"):
    entry = {"id": f"id-{i}", "number": number, "type": type_, "author": author}
    if repo is not None:
        entry["repo"] = repo
    return entry


def test_digest_matches_spec_example():
    entries = [e(1, 123, "comment", "alice"), e(2, 7, "assigned", "carol", repo="lab/sim"), e(3, 131, "review", "bob")]
    assert digest(entries) == "inbox: 3 unread — lab/paper#123 comment(alice), lab/sim#7 assigned, lab/paper#131 review(bob)"


def test_digest_shows_an_entry_without_repo_as_a_bare_number():
    assert digest([e(1, 5, "comment", "old", repo=None), e(2, 5, "comment", "new")]) == (
        "inbox: 2 unread — #5 comment(old), lab/paper#5 comment(new)"
    )


def test_digest_keeps_latest_five_and_counts_the_rest():
    entries = [e(i, i, "comment", f"u{i}", repo="o/r") for i in range(8)]
    assert digest(entries) == (
        "inbox: 8 unread — o/r#3 comment(u3), o/r#4 comment(u4), o/r#5 comment(u5), o/r#6 comment(u6), "
        "o/r#7 comment(u7), +3 more"
    )


def test_digest_textless_types_have_no_author():
    assert digest([e(1, 4, "labeled", "erin"), e(2, 4, "issue_opened", "erin")]) == (
        "inbox: 2 unread — lab/paper#4 labeled, lab/paper#4 issue_opened(erin)"
    )


def test_has_unannounced():
    all_entries = [e(i, i, "comment") for i in range(4)]
    unread = all_entries[1:]
    assert has_unannounced(all_entries, unread, None)
    assert has_unannounced(all_entries, unread, "id-2")
    assert not has_unannounced(all_entries, unread, "id-3")
    assert not has_unannounced(all_entries, [], None)
    assert has_unannounced(all_entries, unread, "id-unknown")
