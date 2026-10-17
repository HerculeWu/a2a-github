import subprocess

import pytest

from a2a.gh import GhClient, GhError, etag_equal


def completed(stdout, returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class Recorder:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        return self.result


OK = (
    "HTTP/2.0 200 OK\r\n"
    'Etag: W/"abc"\r\n'
    'Link: <https://api.github.com/repositories/1/issues?page=2>; rel="next", '
    '<https://api.github.com/repositories/1/issues?page=5>; rel="last"\r\n'
    "X-Poll-Interval: 90\r\n"
    "\r\n"
    '[{"number": 1}]'
)


def test_api_parses_status_headers_body_and_next():
    run = Recorder(completed(OK))
    resp = GhClient(run=run).api("repos/o/r/issues?per_page=1")
    assert resp.status == 200
    assert resp.body == [{"number": 1}]
    assert resp.etag == 'W/"abc"'
    assert resp.next_url == "repositories/1/issues?page=2"
    assert resp.headers["x-poll-interval"] == "90"
    assert run.calls[0][:3] == ["gh", "api", "-i"]


def test_api_sends_if_none_match():
    run = Recorder(completed(OK))
    GhClient(run=run).api("repos/o/r/issues", etag='"abc"')
    argv = run.calls[0]
    assert argv[argv.index("-H") + 1] == 'If-None-Match: "abc"'


def test_304_is_not_an_error_even_though_gh_exits_1():
    out = 'HTTP/2.0 304 Not Modified\nEtag: "abc"\n\n'
    resp = GhClient(run=Recorder(completed(out, returncode=1, stderr="gh: HTTP 304"))).api("x")
    assert resp.status == 304
    assert resp.body is None
    assert resp.not_modified


def test_http_error_raises_with_status():
    out = 'HTTP/2.0 404 Not Found\n\n{"message": "Not Found"}'
    with pytest.raises(GhError) as exc:
        GhClient(run=Recorder(completed(out, returncode=1))).api("x")
    assert exc.value.status == 404
    assert "Not Found" in str(exc.value)


def test_failure_without_http_response_raises():
    run = Recorder(completed("", returncode=4, stderr="To get started with GitHub CLI, please run: gh auth login"))
    with pytest.raises(GhError) as exc:
        GhClient(run=run).api("x")
    assert exc.value.status is None
    assert "gh auth login" in str(exc.value)


def test_missing_gh_binary_raises_gh_error():
    def run(argv, **kwargs):
        raise FileNotFoundError("gh")

    with pytest.raises(GhError):
        GhClient(run=run).api("x")


def test_run_returns_stdout_and_raises_on_failure():
    assert GhClient(run=Recorder(completed("diff text"))).run("pr", "diff", "5") == "diff text"
    with pytest.raises(GhError):
        GhClient(run=Recorder(completed("", returncode=1, stderr="boom"))).run("pr", "diff", "5")


def test_etag_equal_ignores_weak_prefix():
    assert etag_equal('W/"abc"', '"abc"')
    assert not etag_equal('"abc"', '"abd"')
    assert not etag_equal(None, '"abc"')


def test_fake_returns_304_when_etag_matches(fake_gh):
    gh = fake_gh(routes={"repos/o/r/issues": {"etag": '"e1"', "body": [1]}})
    assert gh.api("repos/o/r/issues").body == [1]
    assert gh.api("repos/o/r/issues", etag='W/"e1"').status == 304
    assert [c["path"] for c in gh.calls] == ["repos/o/r/issues", "repos/o/r/issues"]


def test_fake_unknown_route_is_404(fake_gh):
    with pytest.raises(GhError) as exc:
        fake_gh().api("nope")
    assert exc.value.status == 404


def test_fake_commands(fake_gh):
    gh = fake_gh(commands={"pr diff 5": "patch"})
    assert gh.run("pr", "diff", "5") == "patch"
    with pytest.raises(GhError):
        gh.run("pr", "diff", "6")
