"""Issued test-launch ownership: recognize only the exact native client this module started.

No SC2 program is started and no Win32 call is made. `subprocess.Popen` and the
psutil module are replaced by in-memory fakes; the real `editor._launch`,
`editor.processes` and capture guard code paths run. Static expectations only --
neither editor nor runtime acceptance. The module is executed by Codex.
"""
from pathlib import Path

import pytest

from sc2_mcp import editor
from sc2_mcp.errors import SC2Error


def fixture(tmp_path):
    root = tmp_path / "StarCraft II"
    root.mkdir()
    key = "a" * 32
    (root / ".build.info").write_text(f"Branch|Active|Build Key|CDN Key|Version|Product\ncn|1|{key}|{'b'*32}|5.0.17.98370|\n")
    config = root / "SC2Data" / "config" / "aa" / "aa" / key
    config.parent.mkdir(parents=True)
    config.write_text("build-uid = s2c\n")
    for name in ("Support64/SC2Editor_x64.exe", "Support64/SC2Switcher_x64.exe", "Versions/Base98370/SC2_x64.exe"):
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"not executed")
    map_path = tmp_path / "地图 with spaces.SC2Map"
    map_path.mkdir()
    (map_path / "DocumentInfo").write_text("<DocInfo/>")
    (map_path / "ComponentList.SC2Components").write_text("<?xml version=\"1.0\"?><Components/>")
    return root, map_path


def other_map(tmp_path):
    path = tmp_path / "别处.SC2Map"
    path.mkdir()
    (path / "DocumentInfo").write_text("<DocInfo/>")
    return path


# Contract observation (relative times): launcher issued at 1794398564.770306,
# native client created at 1794398564.7888732 => +0.0186 s after issue.
ISSUED_AT = 1000.0
CLIENT_CREATED = ISSUED_AT + 0.0186
SWITCHER_PID = 47188
CLIENT_PID = 51872


class FakeProcess:
    """psutil.Process stand-in exposing only the fields editor.processes() reads."""

    def __init__(self, pid, name, exe, cmdline, create_time):
        self.pid = pid
        self.info = {"pid": pid, "name": name, "exe": exe, "cmdline": cmdline,
                     "create_time": create_time, "status": "running", "num_threads": 12}
        self._children = []

    def children(self, recursive=True):
        return list(self._children)

    def name(self):
        return self.info["name"]

    def create_time(self):
        return self.info["create_time"]


class FakePsutil:
    """psutil module stand-in: fixed listing plus live create times by PID.

    Keep a reference and edit `.procs` / `.times` between calls to model process
    exits, PID reuse or stale listings without re-monkeypatching editor.
    """

    Error = editor.psutil.Error

    def __init__(self, procs, times):
        self.procs = list(procs)
        self.times = dict(times)

    def process_iter(self, _attrs):
        return iter(self.procs)

    def Process(self, pid):
        times = self.times

        class Live:
            def create_time(self):
                if pid not in times or times[pid] is None:
                    raise FakePsutil.Error("NoSuchProcess")
                return times[pid]

            def children(self, recursive=True):
                return []

        return Live()


@pytest.fixture
def fake_psutil(monkeypatch):
    fake = FakePsutil([], {})
    monkeypatch.setattr(editor, "psutil", fake)
    return fake


@pytest.fixture(autouse=True)
def clean_state():
    editor._ISSUED_TESTS.clear()
    editor._OWNED.clear()
    yield
    editor._ISSUED_TESTS.clear()
    editor._OWNED.clear()


@pytest.fixture
def no_win32(monkeypatch):
    """Bypass the OS check but make any real Win32 access fail loudly."""
    import ctypes

    monkeypatch.setattr(editor, "_windows", lambda: None)

    def refuse(*a, **kw):
        raise SC2Error("CAPTURE_FAILED", "Win32 access is not attempted in tests")

    monkeypatch.setattr(ctypes, "WinDLL", refuse)


def issue_test_launch(monkeypatch, fake_psutil, root, map_path, issued=ISSUED_AT, plan=None):
    """Call the real _launch: only Popen is faked, and only around that call."""
    plan = plan or editor.build_launch_command(map_path, root, "test")
    seen = {"issued_at_popen": None}

    class Child:
        pid = SWITCHER_PID

    def fake_popen(argv, **kwargs):
        seen["issued_at_popen"] = editor.time.time()
        seen.update(argv=list(argv), shell=kwargs.get("shell"), cwd=kwargs.get("cwd"))
        return Child()

    # The Switcher is already running before the launch check; after Popen it is
    # registered by the real direct path using a real fake create time.
    fake_psutil.procs = [FakeProcess(SWITCHER_PID, "SC2Switcher_x64.exe", plan["argv"][0],
                                     plan["argv"], issued - 0.25)]
    fake_psutil.times = {SWITCHER_PID: issued - 0.25}
    with monkeypatch.context() as patch:
        patch.setattr(editor, "_windows", lambda: None)
        patch.setattr(editor.subprocess, "Popen", fake_popen)
        patch.setattr(editor.time, "time", lambda: issued)
        result = editor._launch(plan)
    assert seen["argv"] == plan["argv"]
    assert seen["shell"] is False
    assert seen["issued_at_popen"] == issued
    assert result["pid"] == SWITCHER_PID
    assert editor._OWNED.get(SWITCHER_PID) == issued - 0.25  # real direct registration ran
    return plan


def native_client(root, map_path, *, pid=CLIENT_PID, created=CLIENT_CREATED, exe=None, cmdline=None):
    exe = str(root / "Versions/Base98370/SC2_x64.exe") if exe is None else exe
    cmdline = ([exe, "-run", str(map_path), "-displaymode", "0", "-preload", "1",
                "-NoUserCheats", "-reloadcheck", "-uid", "s2_cn"] if cmdline is None else cmdline)
    return FakeProcess(pid, "SC2_x64.exe", exe, cmdline, created)


def switcher(root, plan, created=ISSUED_AT - 0.25):
    return FakeProcess(SWITCHER_PID, "SC2Switcher_x64.exe", plan["argv"][0], plan["argv"], created)


def list_with(fake, procs, times):
    """Explicitly swap the fake process table, then run the real processes()."""
    fake.procs, fake.times = list(procs), dict(times)
    return editor.processes()


def assert_client_unowned(fake, root, bound_map, **client_kwargs):
    """Reject a native client; the Switcher may stay owned via its own Popen registration."""
    plan = editor.build_launch_command(bound_map, root, "test") if editor._ISSUED_TESTS else None
    client = native_client(root, bound_map, **client_kwargs)
    procs = ([switcher(root, plan)] if plan else []) + [client]
    times = {client.pid: client.info["create_time"]}
    if plan:
        times[SWITCHER_PID] = ISSUED_AT - 0.25
    listed = {item["pid"]: item for item in list_with(fake, procs, times)}
    assert listed[client.pid]["owned"] is False
    assert client.pid not in editor._OWNED
    assert editor._owned_process(client.pid) is False
    return listed


# --- real issued binding, Switcher already exited ------------------------------------


def test_issued_client_recognized_after_switcher_exits(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    plan = issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    assert [(r["client"], r["map"], r["issued"]) for r in editor._ISSUED_TESTS] == [
        (editor._path_identity(plan["selected_client"]), editor._path_identity(map_path), ISSUED_AT)]
    record = editor._ISSUED_TESTS[0]
    assert (record["launcher_pid"], record["launcher_created"]) == (SWITCHER_PID, ISSUED_AT - 0.25)
    client = native_client(root, map_path)
    # Switcher is gone from the listing; only the native client remains, and it is not
    # reachable through parent discovery because the parent PID is absent.
    listed = list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED})
    assert listed == [{"pid": CLIENT_PID, "name": "SC2_x64.exe",
                       "executable": str(Path(plan["selected_client"]).resolve()),
                       "arguments": client.info["cmdline"], "created": CLIENT_CREATED,
                       "status": "running", "owned": True}]
    assert editor._OWNED[CLIENT_PID] == CLIENT_CREATED
    assert editor._owned_process(CLIENT_PID) is True


def test_switcher_itself_is_not_claimed_by_issued_rule(tmp_path, monkeypatch, fake_psutil):
    """The helper returns the record only for a native client, never for the launcher."""
    root, map_path = fixture(tmp_path)
    plan = issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    args = switcher(root, plan).info
    assert editor._issued_test_match(SWITCHER_PID, args["name"], args["exe"], args["cmdline"],
                                     args["create_time"]) is None
    editor._OWNED.clear()  # ignore the direct Popen registration for this question
    listed = list_with(fake_psutil, [switcher(root, plan)], {SWITCHER_PID: ISSUED_AT - 0.25})
    assert listed[0]["owned"] is False
    assert SWITCHER_PID not in editor._OWNED
    assert len(editor._ISSUED_TESTS) == 1  # nothing consumed by the launcher


def test_issued_record_is_returned_then_consumed_once(tmp_path, monkeypatch, fake_psutil):
    """One issued test claims at most one native client; a later same-map PID is rejected."""
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    record = editor._ISSUED_TESTS[0]
    first = native_client(root, map_path)
    info = first.info
    assert editor._issued_test_match(first.pid, info["name"], info["exe"], info["cmdline"],
                                     info["create_time"]) is record
    assert list_with(fake_psutil, [first], {first.pid: CLIENT_CREATED})[0]["owned"] is True
    assert record not in editor._ISSUED_TESTS  # consumed after the live check
    assert editor._ISSUED_TESTS == []
    # The first client exits; a second PID starts on the same map well inside 120 s.
    second = native_client(root, map_path, pid=51999, created=ISSUED_AT + 30)
    listed = list_with(fake_psutil, [second], {second.pid: ISSUED_AT + 30})
    assert listed[0]["owned"] is False
    assert second.pid not in editor._OWNED


def test_failed_live_check_does_not_consume_record(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path)
    # Listing claims the bound create time, but the live process has a different one.
    list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED + 900})
    assert client.pid not in editor._OWNED
    assert len(editor._ISSUED_TESTS) == 1


def test_editor_mode_launch_records_nothing(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    plan = editor.build_launch_command(map_path, root, "editor")
    with monkeypatch.context() as patch:
        patch.setattr(editor, "_windows", lambda: None)
        patch.setattr(editor.subprocess, "Popen", lambda *a, **kw: type("Child", (), {"pid": SWITCHER_PID})())
        editor._launch(plan)
    assert editor._ISSUED_TESTS == []


def test_failed_popen_records_nothing(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)

    def boom(*a, **kw):
        raise OSError("denied")

    with monkeypatch.context() as patch:
        patch.setattr(editor, "_windows", lambda: None)
        patch.setattr(editor.subprocess, "Popen", boom)
        with pytest.raises(SC2Error) as err:
            editor._launch(editor.build_launch_command(map_path, root, "test"))
    assert err.value.code == "LAUNCH_FAILED"
    assert editor._ISSUED_TESTS == []
    assert_client_unowned(fake_psutil, root, map_path)


def test_stale_records_retired_on_next_issue(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    editor._ISSUED_TESTS.append({"client": "x", "map": "y", "issued": ISSUED_AT - 500})
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    assert [record["issued"] for record in editor._ISSUED_TESTS] == [ISSUED_AT]
    client = native_client(root, map_path)
    info = client.info
    # The retired record can never be returned again.
    assert editor._issued_test_match(client.pid, info["name"], info["exe"], info["cmdline"],
                                     info["create_time"])["issued"] == ISSUED_AT


# --- rejection: no binding / wrong binding --------------------------------------------


def test_no_issued_launch_rejects_identical_client(tmp_path, fake_psutil):
    root, map_path = fixture(tmp_path)
    assert_client_unowned(fake_psutil, root, map_path)


def test_wrong_client_executable_rejected(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    assert_client_unowned(fake_psutil, root, map_path, exe=str(tmp_path / "Other" / "SC2_x64.exe"))


def test_wrong_map_rejected(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    assert_client_unowned(fake_psutil, root, map_path, cmdline=[str(root / "Versions/Base98370/SC2_x64.exe"),
                                                               "-run", str(other_map(tmp_path))])


def test_client_from_another_map_binding_rejected(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, other_map(tmp_path))
    assert_client_unowned(fake_psutil, root, map_path)


@pytest.mark.parametrize("suffix", [
    [],
    ["-uid", "s2_cn"],
    ["-run"],                                   # dangling -run
    ["-run", "BOUND", "-run", "BOUND"],         # duplicate
    ["-run", "BOUND", "-run"],                  # valid map plus appended dangling -run
    ["-run", "-uid", "s2_cn"],                  # flag-shaped value
])
def test_bad_run_argument_rejected(tmp_path, monkeypatch, fake_psutil, suffix):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    exe = str(root / "Versions/Base98370/SC2_x64.exe")
    cmdline = [exe] + [str(map_path) if token == "BOUND" else token for token in suffix]
    assert_client_unowned(fake_psutil, root, map_path, cmdline=cmdline)


def test_minimal_valid_run_argv_is_recognized(tmp_path, monkeypatch, fake_psutil):
    """[real exe, -run, bound map] is the legal minimum argv and must be claimed."""
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    exe = str(root / "Versions/Base98370/SC2_x64.exe")
    client = native_client(root, map_path, cmdline=[exe, "-run", str(map_path)])
    listed = list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED})
    assert listed[0]["owned"] is True
    assert editor._ISSUED_TESTS == []  # the single claim consumed the record


@pytest.mark.parametrize("field", ["exe", "cmdline", "create_time"])
def test_missing_listing_field_rejected(tmp_path, monkeypatch, fake_psutil, field):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path)
    client.info[field] = None
    listed = list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED})
    assert listed[0]["owned"] is False
    assert client.pid not in editor._OWNED


@pytest.mark.parametrize("malformed", [
    42,                                        # not a sequence at all
    ["SC2_x64.exe", 5, "-run"],                # non-string token
    "SC2_x64.exe -run map",                    # whole argv as one string
    None,
])
def test_malformed_cmdline_rejected_without_type_error(tmp_path, monkeypatch, fake_psutil, malformed):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path)
    client.info["cmdline"] = malformed
    # The redacted log view must not raise and must not invent owned=True.
    listed = list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED})
    assert listed[0]["owned"] is False
    assert listed[0]["arguments"] == []
    assert client.pid not in editor._OWNED
    assert editor._owned_process(client.pid) is False


def test_executable_comes_from_listing_not_argv0(tmp_path, monkeypatch, fake_psutil):
    """A bare argv[0] basename is fine; only the listing executable identifies the client."""
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path, cmdline=["SC2_x64.exe", "-run", str(map_path)])
    listed = list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED})
    assert listed[0]["owned"] is True


def test_argv_without_argv0_or_short_rejected(tmp_path, monkeypatch, fake_psutil):
    """['-run', map] has no argv[0] and fewer than three tokens: strict protocol rejects it."""
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    assert_client_unowned(fake_psutil, root, map_path, cmdline=["-run", str(map_path)])


# --- rejection: timing ----------------------------------------------------------------


@pytest.mark.parametrize("offset", [-600.0, -0.5, -0.01, 120.5])
def test_client_outside_issue_window_rejected(tmp_path, monkeypatch, fake_psutil, offset):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    created = ISSUED_AT + offset
    assert_client_unowned(fake_psutil, root, map_path, created=created)


def test_client_created_before_issue_rejected_even_if_issued_later(tmp_path, fake_psutil, monkeypatch):
    """Contract: clients created before the launch was issued are never claimed."""
    root, map_path = fixture(tmp_path)
    client = native_client(root, map_path, created=ISSUED_AT - 0.5)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    listed = list_with(fake_psutil, [client], {client.pid: client.info["create_time"]})
    assert listed[0]["owned"] is False


@pytest.mark.parametrize("offset", [0.0, 120.0])
def test_window_edges_inclusive(tmp_path, monkeypatch, fake_psutil, offset):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path, created=ISSUED_AT + offset)
    assert list_with(fake_psutil, [client], {client.pid: client.info["create_time"]})[0]["owned"] is True


# --- rejection: live identity ----------------------------------------------------------


def test_pid_reuse_rejected_when_create_time_mismatches(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path)
    assert list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED})[0]["owned"] is True
    # PID 51872 exited; the listing still shows it, but the live create time is a recycled one.
    editor._OWNED.clear()
    assert list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED + 500})[0]["owned"] is False
    assert client.pid not in editor._OWNED


def test_live_create_time_mismatch_blocks_new_claim(tmp_path, monkeypatch, fake_psutil):
    """The listing's created must agree with psutil.Process(pid) before _OWNED is written."""
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path)
    assert list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED + 900})[0]["owned"] is False
    assert client.pid not in editor._OWNED


def test_existing_ownership_with_other_create_time_fails_closed(tmp_path, monkeypatch, fake_psutil):
    """A stale _OWNED start time is never overwritten by a new listing-based claim."""
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path)
    editor._OWNED[client.pid] = CLIENT_CREATED - 600  # stale claim for a previous process
    listed = list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED})
    assert listed[0]["owned"] is False
    assert editor._OWNED[client.pid] == CLIENT_CREATED - 600  # retained, not replaced
    assert len(editor._ISSUED_TESTS) == 1  # record not consumed by a failed claim


def test_process_exited_before_live_check_is_not_owned(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path)
    listed = list_with(fake_psutil, [client], {})  # listing row survived; process is gone
    assert listed[0]["owned"] is False
    assert client.pid not in editor._OWNED


def test_empty_listing_claims_nothing(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    assert list_with(fake_psutil, [], {}) == []


# --- preserved behaviour --------------------------------------------------------------


def test_live_parent_child_discovery_preserved(tmp_path, monkeypatch, fake_psutil):
    """Child ownership must come from parent discovery, not from the issued rule."""
    root, map_path = fixture(tmp_path)
    editor._ISSUED_TESTS.clear()  # nothing may be claimed by the issued rule here
    parent = FakeProcess(SWITCHER_PID, "SC2Switcher_x64.exe", str(root / "Support64/SC2Switcher_x64.exe"),
                         [str(root / "Support64/SC2Switcher_x64.exe"), "-run", str(map_path)], 3000.0)
    child = native_client(root, map_path, created=3000.05)
    parent._children = [child]
    editor._OWNED[SWITCHER_PID] = 3000.0  # explicit ownership from this service's own launch
    visible = {SWITCHER_PID: 3000.0, child.pid: 3000.05}
    first = list_with(fake_psutil, [parent], visible)  # child not yet listed in this table
    assert [(item["pid"], item["owned"]) for item in first] == [(SWITCHER_PID, True)]
    assert editor._OWNED[child.pid] == 3000.05  # discovered via the live parent
    second = list_with(fake_psutil, [parent, child], visible)
    assert [(item["pid"], item["owned"]) for item in second] == [(SWITCHER_PID, True), (CLIENT_PID, True)]
    # A parent that has since exited stays in _OWNED (current implementation keeps it)
    # and still returns True from the identity check.
    assert list_with(fake_psutil, [], visible) == []
    assert editor._owned_process(SWITCHER_PID) is True


def test_concurrent_consumption_blocks_late_claim(tmp_path, monkeypatch, fake_psutil):
    """Consumption must succeed to claim; an already-consumed record grants nothing."""
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path)
    info = client.info
    # A concurrent query matched the same record first and consumed it.
    matched = editor._issued_test_match(client.pid, info["name"], info["exe"], info["cmdline"],
                                       info["create_time"])
    assert editor._consume_issued_tests(matched) is True
    assert editor._ISSUED_TESTS == []
    # A second query that still holds the stale record cannot claim anything.
    assert editor._consume_issued_tests(matched) is False
    listed = list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED})
    assert listed[0]["owned"] is False
    assert client.pid not in editor._OWNED


def test_double_scan_claims_only_once(tmp_path, monkeypatch, fake_psutil):
    """After the record is consumed, a repeat matching scan cannot claim the same process again."""
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path)
    info = client.info
    assert editor._issued_test_match(client.pid, info["name"], info["exe"], info["cmdline"],
                                     info["create_time"]) is not None
    assert editor._consume_issued_tests(editor._ISSUED_TESTS[0]) is True
    # Two further matching listings find no pending record, so neither may claim.
    for _ in range(2):
        listed = list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED})
        assert listed[0]["owned"] is False
    assert client.pid not in editor._OWNED


def test_parent_discovery_consumes_launcher_record(tmp_path, monkeypatch, fake_psutil):
    """Live-parent discovery -> original client gone -> same-map new PID is rejected."""
    root, map_path = fixture(tmp_path)
    plan = issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    assert len(editor._ISSUED_TESTS) == 1
    parent = switcher(root, plan)
    client = native_client(root, map_path, created=ISSUED_AT + 0.05)
    parent._children = [client]
    times = {SWITCHER_PID: ISSUED_AT - 0.25, client.pid: ISSUED_AT + 0.05}
    listed = list_with(fake_psutil, [parent], times)  # child is found via the live parent
    assert [(item["pid"], item["owned"]) for item in listed] == [(SWITCHER_PID, True)]
    assert editor._OWNED[client.pid] == ISSUED_AT + 0.05
    assert editor._ISSUED_TESTS == []  # launcher record consumed by trusted discovery
    # The original client exits; another PID starts on the same map inside 120 s.
    editor._OWNED.pop(client.pid)
    replacement = native_client(root, map_path, pid=52000, created=ISSUED_AT + 10)
    listed = list_with(fake_psutil, [replacement], {replacement.pid: ISSUED_AT + 10})
    assert listed[0]["owned"] is False
    assert replacement.pid not in editor._OWNED


def test_parent_discovery_with_untrusted_parent_keeps_record(tmp_path, monkeypatch, fake_psutil):
    """A parent this service never launched owns nothing, so discovery grants nothing."""
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    foreign = FakeProcess(60050, "SC2Switcher_x64.exe", str(root / "Support64/SC2Switcher_x64.exe"),
                          [str(root / "Support64/SC2Switcher_x64.exe"), "-run", str(map_path)], 5000.0)
    child = native_client(root, map_path, created=5000.05)
    foreign._children = [child]
    list_with(fake_psutil, [foreign], {60050: 5000.0, child.pid: 5000.05})
    assert foreign.pid not in editor._OWNED  # never entered _OWNED by this service
    assert child.pid not in editor._OWNED  # _owned_process guard refuses the untrusted parent
    assert len(editor._ISSUED_TESTS) == 1  # but no issued record was consumed


def test_parent_discovery_without_any_issued_record(tmp_path, fake_psutil):
    """Parent rule works with zero pending records, so nothing can be consumed here."""
    root, map_path = fixture(tmp_path)
    editor._ISSUED_TESTS.clear()
    parent = FakeProcess(SWITCHER_PID, "SC2Switcher_x64.exe", str(root / "Support64/SC2Switcher_x64.exe"),
                         ["SC2Switcher_x64.exe", "-run", str(map_path)], 2000.0)
    client = native_client(root, map_path, created=2000.05)
    parent._children = [client]
    editor._OWNED[SWITCHER_PID] = 2000.0  # explicit, direct ownership from a real launch
    list_with(fake_psutil, [parent, client], {SWITCHER_PID: 2000.0, client.pid: 2000.05})
    assert set(editor._OWNED) == {SWITCHER_PID, CLIENT_PID}
    assert editor._ISSUED_TESTS == []


def test_installation_root_filter_still_excludes_foreign_processes(tmp_path, monkeypatch, fake_psutil):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    outside = native_client(root, map_path, exe=str(tmp_path / "elsewhere" / "SC2_x64.exe"))
    fake_psutil.procs, fake_psutil.times = [outside], {outside.pid: CLIENT_CREATED}
    assert editor.processes(root) == []
    assert outside.pid not in editor._OWNED


# --- path identity --------------------------------------------------------------------


def test_path_identity_normalizes_case_and_rejects_bad_types(tmp_path):
    path = tmp_path / "Map.SC2Map"
    assert editor._path_identity(str(path)) == editor._path_identity(str(path).upper())
    for bad in (None, 42, b"bytes", "", object()):
        assert editor._path_identity(bad) is None


# --- capture guards: unchanged, still strict ------------------------------------------


@pytest.mark.parametrize("case", ["no_issued", "wrong_map", "outside_window", "wrong_client", "no_run",
                                  "live_mismatch"])
def test_capture_refuses_every_unrecognized_client(tmp_path, monkeypatch, fake_psutil, no_win32, case):
    root, map_path = fixture(tmp_path)
    created = CLIENT_CREATED
    client = native_client(root, map_path)
    if case != "no_issued":
        issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    if case == "wrong_map":
        client = native_client(root, map_path, cmdline=[str(root / "Versions/Base98370/SC2_x64.exe"),
                                                        "-run", str(other_map(tmp_path))])
    elif case == "outside_window":
        created = ISSUED_AT - 300
        client = native_client(root, map_path, created=created)
    elif case == "wrong_client":
        client = native_client(root, map_path, exe=str(tmp_path / "elsewhere" / "SC2_x64.exe"))
    elif case == "no_run":
        client = native_client(root, map_path, cmdline=[str(root / "Versions/Base98370/SC2_x64.exe")])
    elif case == "live_mismatch":
        created = CLIENT_CREATED + 900
    list_with(fake_psutil, [client], {client.pid: created})
    for api in (editor.capture_window, editor.capture_visible_window):
        output = tmp_path / f"{case}-{api.__name__}.png"
        with pytest.raises(SC2Error) as err:
            api(client.pid, output)
        assert err.value.code == "PROCESS_NOT_OWNED"
        assert not output.exists()


@pytest.mark.parametrize("api_name", ["capture_window", "capture_visible_window"])
def test_capture_lets_recognized_client_past_guard(tmp_path, monkeypatch, fake_psutil, no_win32, api_name):
    root, map_path = fixture(tmp_path)
    issue_test_launch(monkeypatch, fake_psutil, root, map_path)
    client = native_client(root, map_path)
    list_with(fake_psutil, [client], {client.pid: CLIENT_CREATED})
    output = tmp_path / f"{api_name}.png"
    with pytest.raises(SC2Error) as err:
        getattr(editor, api_name)(client.pid, output)
    assert err.value.code != "PROCESS_NOT_OWNED"  # fails later, not at the ownership guard
    assert not output.exists()
