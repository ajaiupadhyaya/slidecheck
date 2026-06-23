from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Finding:
    check_id: str
    severity: Severity
    slide_index: int
    message: str
    shape_ref: str | None = None
    suggestion: str | None = None
    auto_fixed: bool = False


@dataclass
class Change:
    fixer_id: str
    slide_index: int
    description: str
    shape_ref: str | None = None
    machine_generated: bool = False


@dataclass
class FileResult:
    source_path: str
    output_path: str | None = None
    findings: list[Finding] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    error: str | None = None
