"""XML helpers for BPMN generation and validation."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

from lxml import etree

NS_BPMN = "http://www.omg.org/spec/BPMN/20100524/MODEL"
NS_BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"
NS_DC = "http://www.omg.org/spec/DD/20100524/DC"
NS_DI = "http://www.omg.org/spec/DD/20100524/DI"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_ZEEBE = "http://camunda.org/schema/zeebe/1.0"

SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_]")


def safe_id(candidate: str, prefix: str = "id") -> str:
    """Coerce an arbitrary string into a valid BPMN NCName-like id."""
    cleaned = SAFE_ID_RE.sub("_", str(candidate)).strip("_")
    if not cleaned:
        cleaned = f"{prefix}_{uuid.uuid4().hex[:8]}"
    if cleaned[0].isdigit():
        cleaned = f"{prefix}_{cleaned}"
    return cleaned[:80]


def output_file(folder: Path, process_id: str, suffix: str, stamp: str | None = None) -> Path:
    """Resolve a write path that cannot escape ``folder``."""
    root = folder.resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = safe_id(process_id, "process")
    filename = f"{name}_{stamp}{suffix}" if stamp else f"{name}{suffix}"
    path = (root / filename).resolve()
    path.relative_to(root)
    return path


def build_root(process_id: str) -> etree._Element:
    """Create the <bpmn:definitions> root with Camunda/bpmn-js namespaces."""
    nsmap = {
        "bpmn": NS_BPMN,
        "bpmndi": NS_BPMNDI,
        "dc": NS_DC,
        "di": NS_DI,
        "xsi": NS_XSI,
        "zeebe": NS_ZEEBE,
    }
    return etree.Element(
        f"{{{NS_BPMN}}}definitions",
        nsmap=nsmap,
        id=f"Definitions_{safe_id(process_id)}",
        targetNamespace="http://bpmn.io/schema/bpmn",
    )


def pretty_xml(root: etree._Element) -> str:
    raw = etree.tostring(
        root,
        encoding="utf-8",
        pretty_print=True,
        xml_declaration=True,
    )
    return raw.decode("utf-8")


def parse_xml(text: str) -> Optional[etree._Element]:
    try:
        return etree.fromstring(text.encode("utf-8"))
    except (etree.XMLSyntaxError, ValueError):
        return None
