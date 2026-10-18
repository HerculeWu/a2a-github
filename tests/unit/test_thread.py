import pytest

from a2a.thread import ThreadNameError, format_thread, parse_thread

ONE = ["lab/paper"]
TWO = ["lab/paper", "lab/sim"]


@pytest.mark.parametrize("token", ["lab/sim#7", "LAB/Sim#7"])
def test_owner_name_number_resolves_to_the_stored_spelling(token):
    ref = parse_thread(token, TWO)
    assert (ref.repo, ref.number, ref.bare) == ("lab/sim", 7, False)


def test_a_repo_outside_repos_keeps_its_own_spelling():
    ref = parse_thread("Other/Thing#3", TWO)
    assert (ref.repo, ref.number, ref.bare) == ("Other/Thing", 3, False)


@pytest.mark.parametrize("token", ["#12", "12"])
def test_a_bare_number_resolves_only_with_one_repo(token):
    ref = parse_thread(token, ONE)
    assert (ref.repo, ref.number, ref.bare) == ("lab/paper", 12, True)
    with pytest.raises(ThreadNameError) as e:
        parse_thread(token, TWO)
    assert str(e.value) == "ambiguous: #12 — use owner/name#12 (repos: lab/paper, lab/sim)"


@pytest.mark.parametrize("token", [
    "https://github.com/lab/sim/issues/7",
    "lab/sim 7",
    "sim#7",
    "lab/sim#0",
    "#0",
    "-3",
    "lab/sim#",
    "lab/sim#7x",
    "#",
    "lab/sim/x#7",
])
def test_other_forms_are_usage_errors(token):
    with pytest.raises(ThreadNameError):
        parse_thread(token, ONE)


def test_format():
    assert format_thread("lab/sim", 7) == "lab/sim#7"
    assert format_thread(None, 7) == "#7"
