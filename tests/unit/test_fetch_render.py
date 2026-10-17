from datetime import datetime, timezone

from a2a.fetch import Post, ThreadView, after, fit

T = lambda h, m=0: datetime(2026, 10, 17, h, m, tzinfo=timezone.utc)  # noqa: E731


def view(n_posts=5, body="The body text.", since=None):
    posts = [Post(author=f"u{i}", login=f"u{i}", ts=T(10 + i), text=f"comment number {i} " + "x" * 40) for i in range(n_posts)]
    return ThreadView(header="# #7 Title [open]\nalice · 2026-10-17T09:00Z · https://x", body=body, posts=posts,
                      total=n_posts, since=since)


def test_after_keeps_only_later_posts():
    posts = view().posts
    assert [p.author for p in after(posts, T(12))] == ["u3", "u4"]
    assert after(posts, None) == posts


def test_full_render_when_it_fits():
    out = fit(view(2), None)
    assert out.text == (
        "# #7 Title [open]\nalice · 2026-10-17T09:00Z · https://x\n\n"
        "The body text.\n\n"
        "## Comments (2)\n"
        "### u0 · 2026-10-17T10:00Z\ncomment number 0 " + "x" * 40 + "\n\n"
        "### u1 · 2026-10-17T11:00Z\ncomment number 1 " + "x" * 40
    )
    assert not out.truncated


def test_since_heading():
    v = view(5, since=T(12))
    v.posts = after(v.posts, T(12))
    assert "## Comments (2 of 5 after 2026-10-17T12:00Z)" in fit(v, None).text


def test_truncation_keeps_header_and_newest_comments():
    v = view(10)
    out = fit(v, 400)
    assert len(out.text) <= 400
    assert out.truncated
    assert out.text.startswith("# #7 Title [open]")
    assert "comment number 9" in out.text
    assert "comment number 0" not in out.text
    assert f"[truncated: {out.omitted} earlier comments omitted]" in out.text
    kept = [p.author for p in out.posts]
    assert kept == [f"u{i}" for i in range(10 - len(kept), 10)]


def test_truncation_cuts_long_body_to_a_quarter():
    out = fit(view(1, body="B" * 1000), 400)
    assert "B" * 100 + " [truncated]" in out.text
    assert "B" * 101 not in out.text
    assert len(out.text) <= 400


def test_truncation_keeps_head_of_newest_comment_when_none_fit():
    v = view(0)
    v.posts = [Post(author="big", login="big", ts=T(10), text="Y" * 1000)]
    v.total = 1
    out = fit(v, 300)
    assert len(out.text) <= 300
    assert out.text.endswith(" [truncated]")
    assert "### big" in out.text


def test_comments_only_has_no_body():
    v = view(1, body=None)
    assert "The body text." not in fit(v, None).text


def test_review_post_render():
    p = Post(author="bob", login="bob", ts=T(10), text="Looks good", kind="review", state="APPROVED",
             inline=["a.py:3: nit"])
    assert p.render() == "### bob · review APPROVED · 2026-10-17T10:00Z\nLooks good\n- a.py:3: nit"


def test_budget_is_never_exceeded():
    for budget in (30, 60, 90, 120, 150, 200, 260, 400, 800):
        for v in (view(10), view(1, body="B" * 1000), view(0, body="C" * 500)):
            out = fit(v, budget)
            assert len(out.text) <= budget, (budget, out.text)
