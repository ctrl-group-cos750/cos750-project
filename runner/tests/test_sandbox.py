"""The sandbox, run directly: grading, the friendly messages, and hostile code (NFR-S7).

Network access and the read-only filesystem are the container's job; tests/container_check.py
checks those against the real image in CI.
"""

import json

import pytest

from runner.models import TestCase
from runner.sandbox import LIMITS, Limits, execute

FAST = Limits(cpu_seconds=1, wall_seconds=3)

BFS = """
from collections import deque

def bfs(graph, start):
    order, seen, queue = [], {start}, deque([start])
    while queue:
        v = queue.popleft()
        order.append(v)
        for n in sorted(graph[v]):
            if n not in seen:
                seen.add(n)
                queue.append(n)
    return order
"""
GRAPH = "{'A': ['C', 'B'], 'B': ['D'], 'C': ['D'], 'D': []}"


def call(name: str, expr: str, expected: object, **extra: object) -> TestCase:
    return TestCase.model_validate(
        {"name": name, "kind": "call", "call": expr, "expected": expected, **extra}
    )


def code(name: str, body: str, **extra: object) -> TestCase:
    return TestCase.model_validate({"name": name, "kind": "code", "code": body, **extra})


# Grading


def test_correct_code_passes_every_test() -> None:
    result = execute(BFS, [call("small graph", f"bfs({GRAPH}, 'A')", ["A", "B", "C", "D"])])
    assert result.outcome == "completed"
    assert result.message is None
    assert [(t.name, t.passed, t.message) for t in result.tests] == [("small graph", True, None)]


def test_a_hidden_test_never_shows_the_expected_answer() -> None:
    result = execute(BFS, [call("hidden", f"bfs({GRAPH}, 'A')", ["A", "C", "B", "D"])])
    assert not result.tests[0].passed
    assert result.tests[0].message == "This test didn't pass."


def test_a_visible_test_shows_what_came_back() -> None:
    result = execute(BFS, [call("example", "bfs({'A': []}, 'A')", ["B"], visible=True)])
    assert result.tests[0].message == "bfs({'A': []}, 'A') returned [\"A\"], expected [\"B\"]."


def test_an_authors_message_wins() -> None:
    hint = "Is A added to visited before it is queued?"
    result = execute(BFS, [call("hidden", "bfs({'A': []}, 'A')", ["B"], message=hint)])
    assert result.tests[0].message == hint


def test_tuples_and_sets_compare_as_lists() -> None:
    result = execute(
        "def f():\n    return (1, 2), {3, 1, 2}",
        [call("tuple and set", "f()", [[1, 2], [1, 2, 3]])],
    )
    assert result.tests[0].passed


def test_a_value_that_cant_be_compared_fails_clearly() -> None:
    result = execute(
        "def f():\n    return object()", [call("odd value", "f()", None, visible=True)]
    )
    assert result.outcome == "completed"
    assert result.tests[0].message == "TypeError: a object can't be compared"


def test_code_tests_pass_when_they_run_without_error() -> None:
    result = execute(
        BFS,
        [
            code("passes", "assert bfs({'A': []}, 'A') == ['A']", visible=True),
            code("fails", "assert bfs({'A': []}, 'A') == ['B'], 'start comes first'", visible=True),
            code("authored", "assert False", visible=True, message="Check the start vertex."),
        ],
    )
    assert [t.passed for t in result.tests] == [True, False, False]
    assert result.tests[1].message == "AssertionError: start comes first"
    assert result.tests[2].message == "Check the start vertex."


def test_an_error_inside_one_test_does_not_stop_the_rest() -> None:
    result = execute(
        "def f(x):\n    return 10 // x",
        [call("zero", "f(0)", 0), call("two", "f(2)", 5)],
    )
    assert [t.passed for t in result.tests] == [False, True]
    assert result.tests[0].message == "Your code raised ZeroDivisionError on this test."


def test_print_output_comes_back() -> None:
    result = execute("print('hello')\nimport sys\nprint('oops', file=sys.stderr)", [])
    assert (result.stdout, result.stderr) == ("hello\n", "oops\n")


# What the student sees when something goes wrong (FR-5.6)


def test_a_syntax_error_says_where() -> None:
    result = execute("def bfs(graph start):\n    pass", [call("t", "bfs(1, 2)", None)])
    assert result.outcome == "syntax_error"
    assert result.message is not None
    assert "(line 1)" in result.message
    assert result.tests[0].message == "Not run: your code stopped first."


def test_an_error_while_loading_says_which_line() -> None:
    result = execute("x = 1\ny = [][3]", [])
    assert result.outcome == "error"
    assert result.message == "Your code raised IndexError on line 2: list index out of range"


def test_exiting_early_is_reported() -> None:
    result = execute("import sys\nsys.exit(3)", [])
    assert result.outcome == "error"
    assert result.message is not None
    assert result.message.startswith("Your code raised SystemExit")


# Hostile code (NFR-S7)


def test_an_infinite_loop_is_stopped_by_the_cpu_limit() -> None:
    result = execute("while True:\n    pass", [], FAST)
    assert result.outcome == "timeout"
    assert result.message == (
        "Your code took longer than 1 seconds. Check for a loop that never ends."
    )
    assert result.duration_ms < 2500


def test_ignoring_the_cpu_signal_does_not_help() -> None:
    hostile = "import signal\nsignal.signal(signal.SIGXCPU, signal.SIG_IGN)\nwhile True:\n    pass"
    assert execute(hostile, [], FAST).outcome == "timeout"


def test_sleeping_is_stopped_by_the_wall_clock() -> None:
    result = execute("import time\ntime.sleep(60)", [], FAST)
    assert result.outcome == "timeout"
    assert result.duration_ms < 4000


def test_a_memory_bomb_hits_the_memory_limit() -> None:
    result = execute("x = 'a' * (1024 * 1024 * 1024)", [])
    assert result.outcome == "memory_limit"
    assert result.message is not None
    assert "128 MB" in result.message


def test_a_memory_bomb_inside_a_test_is_caught_too() -> None:
    result = execute("def grow():\n    return [0] * (10 ** 9)", [call("grow", "grow()", [])])
    assert result.outcome == "memory_limit"


def test_huge_output_is_cut_at_one_megabyte() -> None:
    result = execute("while True:\n    print('x' * 1000)", [])
    assert result.outcome == "output_limit"
    assert len(result.stdout) == LIMITS.output_bytes


def test_a_fork_bomb_cannot_start_a_single_process() -> None:
    bomb = (
        "import os\nfailed = 0\nfor _ in range(50):\n    try:\n        if os.fork() == 0:\n"
        "            os._exit(0)\n    except OSError:\n        failed += 1\nprint(failed)"
    )
    result = execute(bomb, [])
    assert result.stdout == "50\n"


def test_threads_cannot_be_started_either() -> None:
    result = execute(
        "import threading\ntry:\n    threading.Thread(target=print).start()\n    print('started')\n"
        "except RuntimeError:\n    print('refused')",
        [],
    )
    assert result.stdout == "refused\n"


def test_subprocesses_cannot_be_started() -> None:
    result = execute(
        "import subprocess\ntry:\n    subprocess.run(['true'])\n    print('ran')\nexcept OSError:\n"
        "    print('refused')",
        [],
    )
    assert result.stdout == "refused\n"


def test_the_environment_holds_nothing_from_the_runner() -> None:
    result = execute("import os, json\nprint(json.dumps(dict(os.environ)))", [])
    env = json.loads(result.stdout)
    assert set(env) == {"HOME", "LANG", "PATH", "RESULT_FD"}


def test_the_code_runs_in_its_own_empty_folder_that_is_removed_afterwards() -> None:
    # Even its output files have no name there, so another run has nothing to open.
    result = execute("import os\nprint(os.getcwd())\nprint(sorted(os.listdir('.')))", [])
    folder, listing = result.stdout.splitlines()
    assert listing == "[]"
    import os

    assert not os.path.exists(folder)


def test_writing_a_file_is_refused() -> None:
    result = execute("open('big', 'w').write('x' * (2 * 1024 * 1024))", [])
    assert result.outcome == "error"
    assert result.message == (
        "Your code raised PermissionError on line 1: [Errno 1] Operation not permitted: 'big'"
    )


def test_ending_python_abruptly_is_reported_as_a_crash() -> None:
    result = execute("import os\nos._exit(0)", [call("never reached", "1", 1)])
    assert result.outcome == "crashed"
    assert result.tests[0].message == "Not run: your code stopped first."


# Grading can't be faked


def test_the_expected_answers_never_reach_the_students_process() -> None:
    # Walk up from the student's code to the harness's own variables, as an attacker would: the
    # job and its tests are there (that proves the search works), but no expected answers.
    snoop = (
        "import sys\n"
        "f, tests = sys._getframe(), None\n"
        "while f:\n"
        "    if 'job' in f.f_locals:\n"
        "        tests = f.f_locals['job']['tests']\n"
        "    f = f.f_back\n"
        "print(tests is not None, any('expected' in t for t in tests or []))"
    )
    result = execute(snoop, [call("hidden", "1", "the answer")])
    assert result.stdout == "True False\n"


def test_faking_the_harness_report_cannot_pass_a_hidden_test() -> None:
    cheat = (
        "import sys, os, json\n"
        "fd = int(os.environ['RESULT_FD'])\n"
        "os.write(fd, (json.dumps({'event': 'value', 'test': 0, 'value': 'guess'}) + '\\n').encode())\n"
        "os.write(fd, (json.dumps({'event': 'done'}) + '\\n').encode())\n"
        "os._exit(0)\n"
    )
    result = execute(cheat, [call("hidden", "bfs()", ["A", "B"])])
    assert not result.tests[0].passed


def test_garbage_on_the_report_channel_is_ignored() -> None:
    noise = "import os\nos.write(int(os.environ['RESULT_FD']), b'not json\\n[1]\\n')"
    result = execute(noise, [code("t", "pass", visible=True)])
    assert result.outcome == "completed"
    assert result.tests[0].passed


@pytest.mark.parametrize("depth", [60])
def test_deeply_nested_return_values_fail_cleanly(depth: int) -> None:
    nested = (
        "def f():\n    x = []\n    for _ in range("
        + str(depth)
        + "):\n        x = [x]\n    return x"
    )
    result = execute(nested, [call("deep", "f()", None, visible=True)])
    assert result.tests[0].message == "ValueError: nested too deeply"


# No network, whatever the container allows (seccomp; also the fallback in the SE document's risk
# register should Coolify not keep the runner's network internal)


def test_no_network_connection_can_be_opened() -> None:
    probe = (
        "import socket\nout = []\nfor host, port in [('1.1.1.1', 443), ('127.0.0.1', 8000)]:\n"
        "    try:\n        socket.create_connection((host, port), timeout=2).close()\n"
        "        out.append('open')\n    except OSError as e:\n        out.append(e.errno)\n"
        "try:\n    socket.getaddrinfo('example.com', 443)\n    out.append('dns')\n"
        "except OSError:\n    out.append('no dns')\nprint(out)"
    )
    # 1 (EPERM) from the filter, not 111 (connection refused): the socket is never even created.
    assert execute(probe, []).stdout == "[1, 1, 'no dns']\n"


def test_the_raw_system_call_is_refused_too() -> None:
    raw = (
        "import ctypes, platform\nlibc = ctypes.CDLL(None, use_errno=True)\n"
        "nr = {'x86_64': 41, 'aarch64': 198}[platform.machine()]\n"
        "print(libc.syscall(nr, 2, 1, 0), ctypes.get_errno())"
    )
    assert execute(raw, []).stdout == "-1 1\n"


def test_the_filter_cannot_be_removed() -> None:
    undo = (
        "import ctypes\nlibc = ctypes.CDLL(None, use_errno=True)\n"
        "print(libc.prctl(38, 0, 0, 0, 0), ctypes.get_errno())"  # clear no_new_privs: refused
    )
    assert execute(undo, []).stdout == "-1 1\n"


@pytest.mark.parametrize(
    ("attempt", "args"),
    [
        ("make itself inspectable again", "4, 1"),  # PR_SET_DUMPABLE
        ("stop dying with the runner", "1, 0"),  # PR_SET_PDEATHSIG
    ],
)
def test_what_the_harness_set_up_stays_set(attempt: str, args: str) -> None:
    probe = (
        "import ctypes\nlibc = ctypes.CDLL(None, use_errno=True)\n"
        f"print(libc.prctl({args}, 0, 0, 0), ctypes.get_errno())"
    )
    assert execute(probe, []).stdout == "-1 1\n"


# Other processes are out of reach: student code runs as the same user as the runner


@pytest.mark.parametrize(
    ("attempt", "call"),
    [
        ("kill the runner", "os.kill(os.getppid(), signal.SIGKILL)"),
        ("kill every process of this user", "os.kill(-1, signal.SIGKILL)"),
        (
            "cripple the runner's limits",
            "resource.prlimit(os.getppid(), resource.RLIMIT_NOFILE, (0, 0))",
        ),
        ("lower the runner's priority", "os.setpriority(os.PRIO_PROCESS, os.getppid(), 19)"),
        ("get a handle on the runner", "os.pidfd_open(os.getppid())"),
    ],
)
def test_the_runner_and_other_runs_are_out_of_reach(attempt: str, call: str) -> None:
    # If the filter failed, the first two would kill this test process: the runner here.
    probe = (
        "import os, resource, signal\ntry:\n    " + call + "\n    print('done')\n"
        "except OSError as e:\n    print('refused', e.errno)"
    )
    assert execute(probe, []).stdout == "refused 1\n"


def test_its_own_process_is_still_its_own() -> None:
    probe = (
        "import os, resource\nos.kill(os.getpid(), 0)\nos.kill(0, 0)\n"
        "resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))\nprint('fine')"
    )
    assert execute(probe, []).stdout == "fine\n"


def test_ending_its_own_process_with_a_signal_is_a_crash_not_a_problem() -> None:
    result = execute("import os, signal\nos.kill(os.getpid(), signal.SIGTERM)", [])
    assert result.outcome == "crashed"


# Round two: files, other runs, output the API stores, the compiler


@pytest.mark.parametrize(
    ("attempt", "call"),
    [
        ("create a file", "open('new.txt', 'w')"),
        ("append to a file", "open('/etc/hostname', 'a')"),
        ("open for reading and writing", "open('/etc/hostname', 'r+')"),
        ("create with os.open", "os.open('x', os.O_CREAT | os.O_RDONLY)"),
        ("truncate with os.open", "os.open('/etc/hostname', os.O_TRUNC)"),
        ("make a folder", "os.mkdir('d')"),
        ("delete a file", "os.unlink('/etc/hostname')"),
        ("rename", "os.rename('/etc/hostname', 'y')"),
        ("hard link", "os.link('/etc/hostname', 'y')"),
        ("symlink", "os.symlink('/etc/hostname', 'y')"),
        ("make a fifo", "os.mkfifo('y')"),
        ("truncate a file", "os.truncate('/etc/hostname', 0)"),
    ],
)
def test_nothing_on_disk_can_be_created_or_changed(attempt: str, call: str) -> None:
    probe = (
        "import os\ntry:\n    "
        + call
        + "\n    print('done')\nexcept OSError as e:\n    print('refused', e.errno)"
    )
    assert execute(probe, []).stdout == "refused 1\n"


def test_files_can_still_be_read_and_modules_imported() -> None:
    probe = "import json, collections, heapq, itertools\nprint(len(open(json.__file__).read()) > 0)"
    assert execute(probe, []).stdout == "True\n"


def test_the_raw_openat_call_with_create_is_refused() -> None:
    raw = (
        "import ctypes, os, platform\nlibc = ctypes.CDLL(None, use_errno=True)\n"
        "nr = {'x86_64': 257, 'aarch64': 56}[platform.machine()]\n"
        "print(libc.syscall(nr, -100, b'x', os.O_CREAT | os.O_WRONLY, 0o600), ctypes.get_errno())"
    )
    assert execute(raw, []).stdout == "-1 1\n"


def test_openat2_is_refused_because_its_flags_cant_be_checked() -> None:
    raw = (
        "import ctypes\nlibc = ctypes.CDLL(None, use_errno=True)\n"
        "print(libc.syscall(437, -100, b'/etc/hostname', 0, 0), ctypes.get_errno())"
    )
    assert execute(raw, []).stdout == "-1 1\n"


def test_x32_system_calls_are_refused() -> None:
    # On x86-64, bit 30 selects the x32 table, a second way to make every call.
    raw = (
        "import ctypes, platform\nlibc = ctypes.CDLL(None, use_errno=True)\n"
        "print(libc.syscall(0x40000000 | 41, 2, 1, 0) if platform.machine() == 'x86_64' else -1,"
        " ctypes.get_errno() if platform.machine() == 'x86_64' else 1)"
    )
    assert execute(raw, []).stdout == "-1 1\n"


def test_ptrace_is_refused() -> None:
    raw = (
        "import ctypes, platform\nlibc = ctypes.CDLL(None, use_errno=True)\n"
        "nr = {'x86_64': 101, 'aarch64': 117}[platform.machine()]\n"
        "print(libc.syscall(nr, 0, 0, 0, 0), ctypes.get_errno())"  # PTRACE_TRACEME
    )
    assert execute(raw, []).stdout == "-1 1\n"


def test_a_run_cannot_see_into_another_run_happening_at_the_same_time() -> None:
    victim = "import time\nprint('private output')\ntime.sleep(2)"
    snoop = (
        "import os, time\ntime.sleep(0.5)\nseen = []\n"
        "for pid in os.listdir('/proc'):\n"
        "    if not pid.isdigit() or int(pid) == os.getpid():\n        continue\n"
        "    try:\n        cmd = open(f'/proc/{pid}/cmdline').read()\n    except OSError:\n        continue\n"
        "    if 'harness.py' not in cmd:\n        continue\n"
        "    for part in ['cwd', 'environ', 'fd', 'mem', 'maps']:\n"
        "        try:\n"
        "            os.readlink(f'/proc/{pid}/cwd') if part == 'cwd' else (os.listdir(f'/proc/{pid}/fd') if part == 'fd' else open(f'/proc/{pid}/{part}', 'rb').read(1))\n"
        "            seen.append(part)\n"
        "        except OSError:\n            pass\n"
        "runs = os.listdir('..')\n"
        "found = [f for r in runs if r != os.path.basename(os.getcwd()) for f in os.listdir(os.path.join('..', r))]\n"
        "print('readable:', seen, 'files in other runs:', found)"
    )
    import threading

    results: dict[str, object] = {}
    other = threading.Thread(target=lambda: results.update(victim=execute(victim, [])))
    other.start()
    # Wait until the other run has locked its /proc entries (its first instruction, before its
    # job arrives). In the milliseconds before, Python is still starting and holds nothing of the
    # student's: the job is only sent after the lock.
    assert _wait_for_locked_run(), "the other run never started"
    spy = execute(snoop, [])
    other.join()
    assert spy.stdout == "readable: [] files in other runs: []\n"


def _wait_for_locked_run(seconds: float = 5) -> bool:
    import time
    from pathlib import Path

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if "harness.py" not in (proc / "cmdline").read_text():
                    continue
                (proc / "environ").read_bytes()  # readable: not locked yet
            except PermissionError:
                return True
            except OSError:
                continue
        time.sleep(0.01)
    return False


def test_output_never_carries_a_nul_to_the_api() -> None:
    nul = "chr(0)"
    result = execute(
        f"import sys\nprint('a' + {nul} + 'b')\nprint({nul}, file=sys.stderr)\nraise ValueError('x' + {nul})",
        [],
    )
    zero = chr(0)
    assert zero not in result.stdout + result.stderr + (result.message or "")
    assert result.stdout == "a" + chr(0xFFFD) + "b\n"


def test_a_test_message_never_carries_a_nul_either() -> None:
    result = execute(
        "def f():\n    raise KeyError('k' + chr(0))",
        [call("visible", "f()", 1, visible=True)],
    )
    assert chr(0) not in (result.tests[0].message or "")


def test_bytes_that_are_not_utf8_come_back_replaced() -> None:
    result = execute("import sys\nsys.stdout.buffer.write(bytes([0xFF, 0x41]))", [])
    assert result.stdout == chr(0xFFFD) + "A"


@pytest.mark.parametrize(
    "bomb",
    ["(" * 200_000 + ")" * 200_000, "x = " + "-" * 90_000 + "1", "x = " + "[" * 5000 + "]" * 5000],
    ids=["nested brackets", "deep unary", "nested lists"],
)
def test_code_that_breaks_the_compiler_is_reported_not_crashed(bomb: str) -> None:
    result = execute(bomb[:100_000], [])
    assert result.outcome in ("syntax_error", "error", "memory_limit")
    assert result.message


def test_hidden_code_tests_are_refused_because_they_could_be_faked() -> None:
    with pytest.raises(ValueError, match="a hidden test must be a call test"):
        TestCase.model_validate({"name": "t", "kind": "code", "code": "assert True"})
