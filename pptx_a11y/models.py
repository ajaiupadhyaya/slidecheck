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
    # standards + remediation metadata (all defaulted for backward-compat)
    sc_refs: list[str] = field(default_factory=list)
    wcag_version: str = ""          # "2.0" | "2.1" | "2.2" | ""
    section508: bool = False
    category: str = ""              # images|structure|color|links|media|motion|document|text
    fixable: bool = False
    fix_action: str | None = None
    current_value: str | None = None
    suggested_value: str | None = None
    target: dict = field(default_factory=dict)


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
