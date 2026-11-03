"""The runner's contract with the API: what POST /run takes and returns. JSON is camelCase."""

from typing import Any, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class TestCase(Model):
    """One test of the student's code.

    "call": `call` is an expression such as `bfs(graph, "A")`; the test passes when it returns
    `expected` (as JSON: tuples compare as lists, sets as sorted lists). The expected answer never
    reaches the process running the student's code. Use these for graded, hidden tests.

    "code": `code` is Python that passes when it runs without an error, usually asserts. Use these
    for visible example tests and for tests the student writes.
    """

    __test__: ClassVar[bool] = False  # a test of student code, not a pytest test class

    name: str = Field(min_length=1, max_length=200)
    kind: Literal["call", "code"]
    call: str | None = Field(default=None, max_length=5_000)
    expected: Any = None
    code: str | None = Field(default=None, max_length=20_000)
    # Visible tests may show their details when they fail; hidden ones show only `message`.
    visible: bool = False
    message: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def has_its_body(self) -> Self:
        if self.kind == "call" and not self.call:
            raise ValueError("a call test needs `call`")
        if self.kind == "code" and not self.code:
            raise ValueError("a code test needs `code`")
        return self


class RunRequest(Model):
    code: str = Field(max_length=100_000)
    tests: list[TestCase] = Field(default_factory=list, max_length=50)


Outcome = Literal[
    "completed",  # the code ran and every test was tried; see each test's result
    "syntax_error",
    "error",  # the code raised an error before the tests ran
    "timeout",
    "memory_limit",
    "output_limit",
    "crashed",  # the process ended without finishing, for example os._exit or a segfault
]


class TestResult(Model):
    __test__: ClassVar[bool] = False

    name: str
    passed: bool
    message: str | None = None


class RunResult(Model):
    outcome: Outcome
    # For anything but "completed": what happened, in words for the student (FR-5.6).
    message: str | None = None
    tests: list[TestResult]
    stdout: str
    stderr: str
    duration_ms: int
