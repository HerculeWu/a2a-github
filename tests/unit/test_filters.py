from datetime import datetime, timezone

import pytest

from a2a.activity import Activity, Thread
from a2a.filters import evaluate
from a2a.workspace import Config, Filters

T = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def cfg(me="me-bot", login=None, **filters):
    return Config(repos=["org/repo"], me=me, login=login or me, filters=Filters(**filters))


def thread(**kw):
    base = dict(number=7, title="Fix the parser", login="alice", body="", assignees=[], labels=[], is_pr=False, url="u")
    return Thread(**{**base, **kw})


def act(type_="comment", text="hello", login="bob", target=None, number=7):
    return Activity(id="c-1", type=type_, ts=T, number=number, login=login, text=text, url="u", target=target)


def matched(a=None, th=None, parts=(), **filters):
    c = filters.pop("config", None) or cfg(**filters)
    d = evaluate(a or act(), th or thread(), set(parts), c)
    return d.matched if d.excluded is None else ("excluded", d.excluded)


# assignee
def test_assignee_thread_state_positive():
    assert matched(th=thread(assignees=["Me-Bot"]), assignee=True) == ["assignee"]


def test_assignee_assigned_event_targeting_me():
    assert matched(a=act("assigned", None, target="me-bot"), assignee=True) == ["assignee"]


def test_assignee_review_requested_targeting_me():
    assert matched(a=act("review_requested", None, target="me-bot"), assignee=True) == ["assignee"]


def test_assignee_negative():
    assert matched(th=thread(assignees=["someone"]), a=act("assigned", None, target="someone"), assignee=True) == []


def test_assignee_disabled():
    assert matched(th=thread(assignees=["me-bot"])) == []


# mentions
@pytest.mark.parametrize("text", ["@me-bot please look", "cc: @ME-BOT.", "(@me-bot)", "@me-bot"])
def test_mentions_positive(text):
    assert matched(a=act(text=text), mentions=True) == ["mentions"]


@pytest.mark.parametrize("text", ["@me-bot-2 please", "email me-bot@example.com", "me-bot without at", "@other"])
def test_mentions_negative(text):
    assert matched(a=act(text=text), mentions=True) == []


def test_mentions_alias_literal_case_insensitive():
    assert matched(a=act(text="Agent-X: can you rebase?"), mentions=True, mention_aliases=["agent-x:"]) == ["mentions"]


def test_mentions_shared_login_uses_me_not_login():
    c = cfg(me="agent-x", login="HerculeWu", mentions=True)
    assert matched(a=act(text="@agent-x go"), config=c) == ["mentions"]
    assert matched(a=act(text="@HerculeWu go"), config=c) == []


# labels
def test_labels_thread_state_positive():
    assert matched(th=thread(labels=["Pin:Me-Bot", "bug"]), labels=["pin:me-bot"]) == ["labels:pin:me-bot"]


def test_labels_labeled_event_positive():
    assert matched(a=act("labeled", None, target="pin:me-bot"), labels=["pin:me-bot"]) == ["labels:pin:me-bot"]


def test_labels_negative_and_one_rule_per_label():
    assert matched(th=thread(labels=["bug"]), labels=["pin:me-bot"]) == []
    assert matched(th=thread(labels=["a", "b"]), labels=["a", "b", "c"]) == ["labels:a", "labels:b"]


# regexes
def test_title_regex():
    assert matched(title_regex=r"(?i)parser") == ["title_regex"]
    assert matched(title_regex=r"^Docs") == []


def test_body_regex_uses_activity_text():
    assert matched(a=act(text="stack trace: KeyError"), body_regex=r"KeyError") == ["body_regex"]
    assert matched(a=act(text="all good"), body_regex=r"KeyError") == []
    assert matched(a=act("labeled", None, target="x"), body_regex=r".") == []


# participated
def test_participated_by_prior_activity():
    assert matched(parts={7}, participated=True) == ["participated"]


def test_participated_by_thread_author():
    assert matched(th=thread(login="me-bot"), participated=True) == ["participated"]


def test_participated_thread_author_by_signature_under_shared_login():
    c = cfg(me="agent-x", login="HerculeWu", participated=True)
    th = thread(login="HerculeWu", body="plan\n<!-- a2a:from=agent-x -->")
    assert matched(th=th, config=c) == ["participated"]
    assert matched(th=thread(login="HerculeWu", body="plan"), config=c) == []


def test_participated_negative():
    assert matched(parts={8}, participated=True) == []


# OR combinations
def test_rules_combine_with_or_and_report_all():
    th = thread(assignees=["me-bot"], labels=["pin:me-bot"], title="Fix the parser")
    a = act(text="@me-bot KeyError")
    got = matched(a=a, th=th, parts={7}, assignee=True, mentions=True, labels=["pin:me-bot"],
                  title_regex="parser", body_regex="KeyError", participated=True)
    assert got == ["assignee", "mentions", "labels:pin:me-bot", "title_regex", "body_regex", "participated"]


def test_one_rule_enough():
    assert matched(a=act(text="@me-bot"), mentions=True, title_regex="nomatch", assignee=True) == ["mentions"]


# exclusions
def test_ignore_self_wins_over_matches():
    assert matched(a=act(text="@me-bot note to self", login="me-bot"), mentions=True) == ("excluded", "ignore_self")


def test_ignore_self_can_be_disabled():
    assert matched(a=act(text="@me-bot", login="me-bot"), mentions=True, ignore_self=False) == ["mentions"]


def test_signed_comment_from_shared_login_is_not_self_for_human():
    # The human (me = login) receives a comment their agent posted under their account.
    a = act(text="done @HerculeWu\n<!-- a2a:from=agent-x -->", login="HerculeWu")
    assert matched(a=a, config=cfg(me="HerculeWu", mentions=True)) == ["mentions"]


def test_agent_ignores_own_signed_comment_under_shared_login():
    a = act(text="@agent-x reminder\n<!-- a2a:from=agent-x -->", login="HerculeWu")
    c = cfg(me="agent-x", login="HerculeWu", mentions=True)
    assert matched(a=a, config=c) == ("excluded", "ignore_self")


def test_textless_activity_is_attributed_to_login():
    a = act("labeled", None, login="HerculeWu", target="pin:agent-x")
    c = cfg(me="agent-x", login="HerculeWu", labels=["pin:agent-x"])
    assert matched(a=a, config=c) == ["labels:pin:agent-x"]


def test_exclude_authors_glob_on_author_or_login():
    assert matched(a=act(text="@me-bot", login="dependabot[bot]"), mentions=True, exclude_authors=["*[bot]"]) == ("excluded", "exclude_authors")
    signed = act(text="@me-bot\n<!-- a2a:from=noisy-agent -->", login="HerculeWu")
    assert matched(a=signed, mentions=True, exclude_authors=["noisy-*"]) == ("excluded", "exclude_authors")
    assert matched(a=act(text="@me-bot", login="bob"), mentions=True, exclude_authors=["*[bot]"]) == ["mentions"]
