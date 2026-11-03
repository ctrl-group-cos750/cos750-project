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
import signal
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
    hard(
        resource.RLIMIT_NOFILE, 16
    )  # also bounds pipe and socket buffers, which count as kernel memory


# seccomp: rules the kernel enforces on this process from here on, which can't be undone:
# - no network sockets, so no connection anywhere (internet, DNS, the API, the database), whatever
#   the Docker network allows;
# - signals and resource limits only for this process itself: student code runs as the same user as
#   the runner, so it could otherwise kill the runner or every other student's run (kill(-1)), or
#   cripple the runner with prlimit;
# - nothing that reaches into other processes: pidfd, ptrace, process_vm_*, priorities, scheduling;
# - no prctl: what the harness set up (non-dumpable, dying with the runner) stays set;
# - no creating, writing, renaming or deleting files: the code has no need to, and it can't fill the
#   shared /tmp or touch another run's folder (opening to read is still allowed);
# - none of the kernel's riskier interfaces, whatever Docker's own profile allows: io_uring (it can
#   open sockets and files without the calls above), namespaces, mounts, chroot, keyrings, eBPF,
#   perf, userfaultfd, modules, kexec, file handles, fanotify, and memfd (memory files that no
#   per-process limit counts, so writing to one could fill the container). Refused with EACCES rather than
#   EPERM, so tests can tell this filter refused them, not Docker's;
# - no calls from another architecture's table, which could be used to get around all of this.
# (Linux: <linux/seccomp.h>, <linux/filter.h>.)
_ARCH: dict[str, dict[str, int]] = {
    "x86_64": {
        "audit": 0xC000003E, "socket": 41, "kill": 62, "tkill": 200, "tgkill": 234,
        "prlimit64": 302, "ptrace": 101, "setpriority": 141, "sched_setparam": 142,
        "sched_setscheduler": 144, "sched_setaffinity": 203, "ioprio_set": 251,
        "process_vm_readv": 310, "process_vm_writev": 311, "pidfd_send_signal": 424, "prctl": 157,
        "pidfd_open": 434, "pidfd_getfd": 438,
        "open": 2, "openat": 257, "openat2": 437, "creat": 85, "mkdir": 83, "mkdirat": 258,
        "unlink": 87, "unlinkat": 263, "rename": 82, "renameat": 264, "renameat2": 316, "link": 86,
        "linkat": 265, "symlink": 88, "symlinkat": 266, "mknod": 133, "mknodat": 259,
        "truncate": 76,
    },
    "aarch64": {
        "audit": 0xC00000B7, "socket": 198, "kill": 129, "tkill": 130, "tgkill": 131,
        "prlimit64": 261, "ptrace": 117, "setpriority": 140, "sched_setparam": 118,
        "sched_setscheduler": 119, "sched_setaffinity": 122, "ioprio_set": 30,
        "process_vm_readv": 270, "process_vm_writev": 271, "pidfd_send_signal": 424, "prctl": 167,
        "pidfd_open": 434, "pidfd_getfd": 438,
        "openat": 56, "openat2": 437, "mkdirat": 34, "unlinkat": 35, "renameat": 38,
        "renameat2": 276, "linkat": 37, "symlinkat": 36, "mknodat": 33, "truncate": 45,
    },
}  # fmt: skip
_REFUSED = (
    "socket", "ptrace", "setpriority", "sched_setparam", "sched_setscheduler", "sched_setaffinity",
    "ioprio_set", "process_vm_readv", "process_vm_writev", "pidfd_send_signal", "pidfd_open",
    "pidfd_getfd", "prctl", "openat2", "creat", "mkdir", "mkdirat", "unlink", "unlinkat", "rename",
    "renameat", "renameat2", "link", "linkat", "symlink", "symlinkat", "mknod", "mknodat",
    "truncate",
)  # fmt: skip
# O_WRONLY | O_RDWR | O_CREAT | O_TRUNC | O_APPEND: any of these in open()'s flags is a write.
_WRITE_FLAGS = 0o1 | 0o2 | 0o100 | 0o1000 | 0o2000
# The kernel interfaces no student code needs (see above): x86_64, aarch64.
_KERNEL = {
    "io_uring_setup": (425, 425),
    "io_uring_enter": (426, 426),
    "io_uring_register": (427, 427),
    "unshare": (272, 97),
    "setns": (308, 268),
    "mount": (165, 40),
    "umount2": (166, 39),
    "chroot": (161, 51),
    "pivot_root": (155, 41),
    "keyctl": (250, 219),
    "add_key": (248, 217),
    "request_key": (249, 218),
    "bpf": (321, 280),
    "perf_event_open": (298, 241),
    "userfaultfd": (323, 282),
    "kcmp": (312, 272),
    "process_madvise": (440, 440),
    "process_mrelease": (448, 448),
    "fsopen": (430, 430),
    "fsconfig": (431, 431),
    "fsmount": (432, 432),
    "fspick": (433, 433),
    "open_tree": (428, 428),
    "move_mount": (429, 429),
    "mount_setattr": (442, 442),
    "init_module": (175, 105),
    "finit_module": (313, 273),
    "delete_module": (176, 106),
    "kexec_load": (246, 104),
    "kexec_file_load": (320, 294),
    "open_by_handle_at": (304, 265),
    "name_to_handle_at": (303, 264),
    "fanotify_init": (300, 262),
    "syslog": (103, 116),
    "sethostname": (170, 161),
    "setdomainname": (171, 162),
    "swapon": (167, 224),
    "swapoff": (168, 225),
    "acct": (163, 89),
    "reboot": (169, 142),
    "quotactl": (179, 60),
    "personality": (135, 92),
    "vhangup": (153, 58),
    "lookup_dcookie": (212, 18),
    "memfd_secret": (447, 447),
    "memfd_create": (319, 279),
    "iopl": (172, None),
    "ioperm": (173, None),
    "modify_ldt": (154, None),
    "uselib": (134, None),
}
_LD_W_ABS, _JEQ, _JGE, _JSET, _RET = 0x20, 0x15, 0x35, 0x45, 0x06
_ALLOW, _ERRNO = 0x7FFF0000, 0x00050000
_ARG0, _ARG1, _ARG2 = 16, 24, 32  # seccomp_data.args[i], low 32 bits (pid_t, flags are ints)


def _assemble(program: list[tuple[object, ...]]) -> bytes:
    """BPF with named jump targets: ("label", name) marks a place; jumps name their targets."""
    places, count = {}, 0
    for item in program:
        if item[0] == "label":
            places[item[1]] = count
        else:
            count += 1
    raw, at = b"", 0
    for item in program:
        if item[0] == "label":
            continue
        code, jt, jf, k = item
        jumps = [t if isinstance(t, int) else places[t] - at - 1 for t in (jt, jf)]
        raw += struct.pack("HBBI", code, *jumps, k)
        at += 1
    return raw


def sandbox_syscalls() -> None:
    nr = _ARCH[platform.machine()]
    me = os.getpid()
    column = 0 if platform.machine() == "x86_64" else 1
    kernel = [n[column] for n in _KERNEL.values() if n[column] is not None]
    program: list[tuple[object, ...]] = [
        (_LD_W_ABS, 0, 0, 4),  # seccomp_data.arch
        (_JEQ, 0, "refuse", nr["audit"]),
        (_LD_W_ABS, 0, 0, 0),  # seccomp_data.nr
        (_JGE, "refuse", 0, 0x40000000),  # x32 calls
        *[(_JEQ, "kernel", 0, number) for number in kernel],
        *[(_JEQ, "refuse", 0, nr[name]) for name in _REFUSED if name in nr],
        *([(_JEQ, "open_flags", 0, nr["open"])] if "open" in nr else []),
        (_JEQ, "openat_flags", 0, nr["openat"]),
        (_JEQ, "self_or_group", 0, nr["kill"]),  # kill(0) is its own group: only itself
        (_JEQ, "self_or_group", 0, nr["prlimit64"]),  # prlimit64(0) is itself (setrlimit)
        (_JEQ, "self", 0, nr["tkill"]),
        (_JEQ, "self", 0, nr["tgkill"]),
        (_RET, 0, 0, _ALLOW),
        ("label", "self_or_group"),
        (_LD_W_ABS, 0, 0, _ARG0),
        (_JEQ, "allow", 0, 0),
        (_JEQ, "allow", "refuse", me),
        ("label", "self"),
        (_LD_W_ABS, 0, 0, _ARG0),
        (_JEQ, "allow", "refuse", me),
        ("label", "open_flags"),
        (_LD_W_ABS, 0, 0, _ARG1),
        (_JSET, "refuse", "allow", _WRITE_FLAGS),
        ("label", "openat_flags"),
        (_LD_W_ABS, 0, 0, _ARG2),
        (_JSET, "refuse", "allow", _WRITE_FLAGS),
        ("label", "kernel"),
        (_RET, 0, 0, _ERRNO | errno.EACCES),
        ("label", "refuse"),
        (_RET, 0, 0, _ERRNO | errno.EPERM),
        ("label", "allow"),
        (_RET, 0, 0, _ALLOW),
    ]
    raw = _assemble(program)
    buf = ctypes.create_string_buffer(raw)

    class Prog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]

    prog = Prog(len(raw) // 8, ctypes.addressof(buf))
    libc = ctypes.CDLL(None, use_errno=True)
    pr_set_no_new_privs, pr_set_seccomp, seccomp_mode_filter = 38, 22, 2
    if libc.prctl(pr_set_no_new_privs, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS")
    if libc.prctl(pr_set_seccomp, seccomp_mode_filter, ctypes.byref(prog), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_SECCOMP")


def make_undumpable() -> None:
    """Closes this process's /proc entries (memory, open files, folder, environment) to every
    other process of the same user, that is, to every other run. Done first, before the job
    arrives: until then, another run could read the job off this process's stdin through /proc."""
    libc = ctypes.CDLL(None, use_errno=True)
    pr_set_pdeathsig, pr_set_dumpable = 1, 4
    if libc.prctl(pr_set_dumpable, 0, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_DUMPABLE")
    # Dies with the runner, so no run can outlive the wall clock the runner enforces.
    if libc.prctl(pr_set_pdeathsig, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_PDEATHSIG")
    # The runner was already gone. (Not "parent is PID 1": in the container the runner is PID 1.)
    if os.getppid() != int(os.environ["RUNNER_PID"]):
        os._exit(1)


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
    make_undumpable()
    report = os.fdopen(int(os.environ["RESULT_FD"]), "w", buffering=1)

    def emit(event: dict[str, object]) -> None:
        report.write(json.dumps(event) + "\n")

    emit({"event": "ready"})  # the runner writes the job only after this
    job = json.loads(sys.stdin.read())
    sandbox_syscalls()  # fails closed: if it can't be set up, no student code runs
    set_limits(job["limits"])
    sys.stdout.reconfigure(errors="replace")  # type: ignore[union-attr]

    try:
        compiled = compile(job["code"], STUDENT, "exec")
    except SyntaxError as e:
        emit({"event": "syntax_error", "message": e.msg, "line": e.lineno})
        return
    except (MemoryError, RecursionError, ValueError) as e:  # code too big or deep to compile
        emit(
            {
                "event": "syntax_error",
                "message": f"{type(e).__name__}: {str(e)[:200]}",
                "line": None,
            }
        )
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
