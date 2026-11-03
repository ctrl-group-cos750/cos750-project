"""Runs inside the sandbox: one process per submission, started by sandbox.py as
`python -I -B harness.py` in an empty temporary directory.

It reads the job (the student's code, the tests and the limits) from stdin, sets the limits on
itself as hard limits the student's code can't raise, then runs the code and the tests. It reports
on the file descriptor named in RESULT_FD, one JSON object per line. For "call" tests it reports
the value the student's function returned: the expected answers stay in the runner's own process,
so nothing here can read them or fake a pass.
"""

import ctypes
import errno
import json
import os
import platform
import resource
import struct
import sys

STUDENT = "your code"


def set_limits(limits: dict[str, int]) -> None:
    def hard(kind: int, value: int) -> None:
        resource.setrlimit(kind, (value, value))

    # Soft below hard: at the soft limit the kernel sends SIGXCPU, which the runner reports as a
    # time-out; code that catches it is killed a second later at the hard limit.
    cpu = limits["cpu_seconds"]
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    hard(resource.RLIMIT_AS, limits["memory_bytes"])
    hard(resource.RLIMIT_FSIZE, limits["output_bytes"])  # stdout and stderr are files
    hard(resource.RLIMIT_NPROC, 0)  # no new processes or threads: a fork bomb stops at once
    hard(resource.RLIMIT_CORE, 0)
    hard(resource.RLIMIT_NOFILE, 32)


# seccomp: the kernel refuses socket(2) to this process from now on, so the student's code can't
# open any network connection (internet, DNS, the API, the database), whatever the Docker network
# allows. It can't be undone. Calls from another architecture's system call table are refused too,
# so they can't be used to get around the rule. (Linux: <linux/seccomp.h>, <linux/filter.h>.)
_ARCH = {"x86_64": (0xC000003E, 41), "aarch64": (0xC00000B7, 198)}  # audit arch, __NR_socket
_LD_W_ABS, _JEQ, _JGE, _RET = 0x20, 0x15, 0x35, 0x06
_ALLOW, _ERRNO = 0x7FFF0000, 0x00050000


def block_network() -> None:
    audit_arch, nr_socket = _ARCH[platform.machine()]
    refuse = _ERRNO | errno.EACCES
    program = [
        (_LD_W_ABS, 0, 0, 4),  # seccomp_data.arch
        (_JEQ, 1, 0, audit_arch),
        (_RET, 0, 0, refuse),  # another architecture's calls
        (_LD_W_ABS, 0, 0, 0),  # seccomp_data.nr
        (_JGE, 0, 1, 0x40000000),
        (_RET, 0, 0, refuse),  # x32 calls
        (_JEQ, 0, 1, nr_socket),
        (_RET, 0, 0, refuse),
        (_RET, 0, 0, _ALLOW),
    ]
    raw = b"".join(struct.pack("HBBI", *ins) for ins in program)
    buf = ctypes.create_string_buffer(raw)

    class Prog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]

    prog = Prog(len(program), ctypes.addressof(buf))
    libc = ctypes.CDLL(None, use_errno=True)
    pr_set_no_new_privs, pr_set_seccomp, seccomp_mode_filter = 38, 22, 2
    if libc.prctl(pr_set_no_new_privs, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS")
    if libc.prctl(pr_set_seccomp, seccomp_mode_filter, ctypes.byref(prog), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_SECCOMP")


def student_line(error: BaseException) -> int | None:
    """The line of the student's code the error came from, if it came from there."""
    line = None
    tb = error.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == STUDENT:
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def plain(value: object, depth: int = 0) -> object:
    """The returned value as JSON-compatible data: tuples become lists, sets sorted lists."""
    if depth > 50:
        raise ValueError("nested too deeply")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [plain(v, depth + 1) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [plain(v, depth + 1) for v in value]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True))
    if isinstance(value, dict):
        return {str(k): plain(v, depth + 1) for k, v in value.items()}
    raise TypeError(f"a {type(value).__name__} can't be compared")


def main() -> None:
    report = os.fdopen(int(os.environ["RESULT_FD"]), "w", buffering=1)

    def emit(event: dict[str, object]) -> None:
        report.write(json.dumps(event) + "\n")

    job = json.loads(sys.stdin.read())
    block_network()  # fails closed: if it can't be set up, no student code runs
    set_limits(job["limits"])
    sys.stdout.reconfigure(errors="replace")  # type: ignore[union-attr]

    try:
        compiled = compile(job["code"], STUDENT, "exec")
    except SyntaxError as e:
        emit({"event": "syntax_error", "message": e.msg, "line": e.lineno})
        return
    namespace: dict[str, object] = {"__name__": "__main__", "__builtins__": __builtins__}
    try:
        exec(compiled, namespace)
    except MemoryError:
        emit({"event": "memory"})
        return
    except BaseException as e:  # SystemExit too: the student's code ended the run
        emit(
            {
                "event": "error",
                "type": type(e).__name__,
                "message": str(e)[:300],
                "line": student_line(e),
            }
        )
        return

    for i, test in enumerate(job["tests"]):
        name = f"test {i + 1}"
        try:
            if test["kind"] == "call":
                value = eval(compile(test["call"], name, "eval"), namespace)
                emit({"event": "value", "test": i, "value": plain(value)})
            else:
                exec(compile(test["code"], name, "exec"), namespace)
                emit({"event": "passed", "test": i})
        except MemoryError:
            emit({"event": "memory"})
            return
        except BaseException as e:
            emit(
                {
                    "event": "failed",
                    "test": i,
                    "type": type(e).__name__,
                    "message": str(e)[:300],
                    "line": student_line(e),
                }
            )
    emit({"event": "done"})


if __name__ == "__main__":
    main()
