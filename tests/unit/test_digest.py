from a2a.notify import digest, has_unannounced


def e(i, number, type_, author="x"):
    return {"id": f"id-{i}", "number": number, "type": type_, "author": author}


def test_digest_matches_spec_example():
    entries = [e(1, 123, "comment", "alice"), e(2, 130, "assigned", "carol"), e(3, 131, "review", "bob")]
    assert digest(entries) == "inbox: 3 unread — #123 comment(alice), #130 assigned, #131 review(bob)"


def test_digest_keeps_latest_five_and_counts_the_rest():
    entries = [e(i, i, "comment", f"u{i}") for i in range(8)]
    assert digest(entries) == (
        "inbox: 8 unread — #3 comment(u3), #4 comment(u4), #5 comment(u5), #6 comment(u6), #7 comment(u7), +3 more"
    )


def test_digest_textless_types_have_no_author():
    assert digest([e(1, 4, "labeled", "erin"), e(2, 4, "issue_opened", "erin")]) == (
        "inbox: 2 unread — #4 labeled, #4 issue_opened(erin)"
    )


def test_has_unannounced():
    all_entries = [e(i, i, "comment") for i in range(4)]
    unread = all_entries[1:]
    assert has_unannounced(all_entries, unread, None)
    assert has_unannounced(all_entries, unread, "id-2")
    assert not has_unannounced(all_entries, unread, "id-3")
    assert not has_unannounced(all_entries, [], None)
    assert has_unannounced(all_entries, unread, "id-unknown")
