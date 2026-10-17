import pytest

from a2a.sign import author_of, sign, signed_by, strip_signature

SIG = "<sub>— agent-x</sub>\n<!-- a2a:from=agent-x -->"


def test_sign_appends_visible_and_hidden_signature():
    assert sign("LGTM, merging.\n", "agent-x") == "LGTM, merging.\n\n" + SIG


def test_sign_empty_body():
    assert sign("", "agent-x") == SIG


def test_sign_replaces_existing_signature_instead_of_doubling():
    once = sign("hello", "agent-x")
    assert sign(once, "agent-y") == "hello\n\n<sub>— agent-y</sub>\n<!-- a2a:from=agent-y -->"
    assert sign(once, "agent-x") == once


def test_sign_rejects_bad_names():
    with pytest.raises(ValueError):
        sign("x", "bad name")


def test_signed_by_and_author():
    text = sign("hi @me-bot", "agent-x")
    assert signed_by(text) == "agent-x"
    assert author_of(text, "HerculeWu") == "agent-x"
    assert signed_by("plain text") is None
    assert author_of("plain text", "HerculeWu") == "HerculeWu"
    assert author_of(None, "HerculeWu") == "HerculeWu"


def test_signed_by_tolerates_spacing_and_takes_first():
    assert signed_by("x <!--a2a:from=one--> y <!-- a2a:from=two -->") == "one"


def test_strip_signature():
    assert strip_signature(sign("body text", "agent-x")) == "body text"
    assert strip_signature("no signature") == "no signature"
    assert strip_signature("only marker <!-- a2a:from=z -->") == "only marker"
    assert strip_signature(None) == ""
