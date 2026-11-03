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
            code("passes", "assert bfs({'A': []}, 'A') == ['A']"),
            code("fails", "assert bfs({'A': []}, 'A') == ['B'], 'start comes first'", visible=True),
            code("hidden fail", "assert False"),
        ],
    )
    assert [t.passed for t in result.tests] == [True, False, False]
    assert result.tests[1].message == "AssertionError: start comes first"
    assert result.tests[2].message == "Your code raised AssertionError on this test."


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
    result = execute("import os\nprint(os.getcwd())\nprint(sorted(os.listdir('.')))", [])
    folder, listing = result.stdout.splitlines()
    assert listing == "['stderr', 'stdout']"
    import os

    assert not os.path.exists(folder)


def test_writing_a_big_file_is_refused_at_the_size_limit() -> None:
    # Python ignores SIGXFSZ, so the write fails with an error instead of ending the process.
    result = execute("open('big', 'w').write('x' * (2 * 1024 * 1024))", [])
    assert result.outcome == "error"
    assert result.message == "Your code raised OSError on line 1: [Errno 27] File too large"


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
    result = execute(noise, [code("t", "pass")])
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
    assert execute(undo, []).stdout == "-1 22\n"


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
