import os
import re
from collections import defaultdict, deque


# ============================================================
# ----------- SMALL HELPERS ----------------------------------
# ============================================================

def _clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\t", " ").strip())


def _normalize_tag(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def _short_covergroup_name(full_name: str) -> str:
    """
    Example:
    $unit_dut_sv_2799966959::out_subscriber::out_cg -> out_cg
    """
    full_name = _clean_ws(full_name)

    if "::" in full_name:
        return full_name.split("::")[-1]

    return full_name


def _to_int(value, default=None):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _to_float(value, default=None):
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _split_csv_line(line: str) -> list[str]:
    """
    XCRG text report is comma-separated, but with many spaces.
    For this report format, simple split by comma is enough.
    """
    return [cell.strip() for cell in line.split(",")]


def _extract_xcrg_section(content: str, section_name: str, next_section_name: str | None = None) -> str:
    """
    Extracts a real XCRG section header, not mentions from comments.

    Real headers look like:
    ::::::::::::::::::::::::::::: Total Summary :::::::::::::::::::::::::::::
    """

    header_pattern = (
        r"^\s*:{5,}\s*"
        + re.escape(section_name)
        + r"\s*:{5,}\s*$"
    )

    header_match = re.search(header_pattern, content, re.IGNORECASE | re.MULTILINE)

    if not header_match:
        return ""

    start = header_match.end()

    if next_section_name:
        next_header_pattern = (
            r"^\s*:{5,}\s*"
            + re.escape(next_section_name)
            + r"\s*:{5,}\s*$"
        )

        next_match = re.search(
            next_header_pattern,
            content[start:],
            re.IGNORECASE | re.MULTILINE,
        )

        if next_match:
            end = start + next_match.start()
            return content[start:end]

    return content[start:]

# ============================================================
# ----------- TOTAL SUMMARY PARSER ----------------------------
# ============================================================

def _extract_total_summary(content: str) -> dict:
    """
    Extracts only the real Total Summary section.
    Ignores mentions from XCRG comments.
    """

    summary_text = _extract_xcrg_section(
        content,
        "Total Summary",
        "CoverGroups Summary"
    )

    if not summary_text:
        summary_text = content

    def find_float(pattern: str, default=0.0):
        m = re.search(pattern, summary_text, re.IGNORECASE)
        return float(m.group(1)) if m else default

    def find_int(pattern: str, default=0):
        m = re.search(pattern, summary_text, re.IGNORECASE)
        return int(m.group(1)) if m else default

    return {
        "coverage_score": find_float(r"Coverage\s+Score\s*:\s*,?\s*([\d.]+)"),
        "total_insts_score": find_float(r"Total\s+Insts\s+Score\s*:\s*,?\s*([\d.]+)"),
        "number_of_tests": find_int(r"Number\s+of\s+Tests\s*:\s*,?\s*(\d+)"),
        "total_covergroups": find_int(r"Total\s+no\s+of\s+Cover\s+Groups\s*:\s*,?\s*(\d+)"),
        "total_instances": find_int(r"Total\s+no\s+of\s+Instances\s*:\s*,?\s*(\d+)"),
    }


# ============================================================
# ----------- DETAILED TABLES PARSER --------------------------
# ============================================================

def _extract_uncovered_bins_from_table_body(body: str) -> list[str]:
    """
    Extracts uncovered bin names from detailed CoverPoint Tables.
    If Vivado does not print detailed bin names clearly, the summary parser
    will still report the number of missing bins.
    """

    bins = []
    in_uncovered = False

    for raw_line in body.splitlines():
        line = raw_line.strip()

        if re.match(r"^(User\s+)?Uncovered bins\b", line, re.IGNORECASE):
            in_uncovered = True
            continue

        if in_uncovered and re.match(r"^(User\s+)?Covered bins\b", line, re.IGNORECASE):
            break

        if in_uncovered and re.match(
            r"^(Cross\s+)?Cover Point Table\s+for Inst\b",
            line,
            re.IGNORECASE,
        ):
            break

        if not in_uncovered:
            continue

        cells = _split_csv_line(raw_line)

        if len(cells) < 2:
            continue

        bin_name = cells[0].strip()
        hit_count = _to_int(cells[1], default=None)

        if not bin_name or bin_name.lower() == "name":
            continue

        if hit_count == 0:
            bins.append(bin_name)

    return list(dict.fromkeys(bins))


def _parse_detailed_bins_by_table_tag(content: str) -> dict:
    """
    Parses detailed Cover Point Table sections and stores uncovered bins
    by (kind, table_tag).

    This is used only to enrich holes from CoverGroups Summary.
    """

    detailed = defaultdict(deque)

    table_pattern = re.compile(
        r"(?P<table_type>Cross Cover Point Table|Cover Point Table)"
        r"\s+for Inst\s*:\s*(?P<instance>.*?),"
        r"\s*Variable\s*:,?\s*(?P<variable>[^\n\r]+)"
        r"\s*\n\s*Table tag\s*:,?\s*(?P<table_tag>[^\n\r]+)"
        r"(?P<body>.*?)(?=\n\s*(?:Cross Cover Point Table|Cover Point Table)\s+for Inst\s*:|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    for match in table_pattern.finditer(content):
        table_type = match.group("table_type")
        table_tag = _normalize_tag(match.group("table_tag"))
        body = match.group("body")

        kind = "cross" if table_type.lower().startswith("cross") else "coverpoint"
        bins = _extract_uncovered_bins_from_table_body(body)

        detailed[(kind, table_tag)].append(bins)

    return detailed


# ============================================================
# ----------- COVERGROUPS SUMMARY PARSER ----------------------
# ============================================================

def _parse_covergroups_summary(content: str) -> list[dict]:
    """
    Main extraction logic.

    It reads:
    - covergroup name
    - instance name
    - instance occurrence index
    - coverpoint/cross name
    - expected/uncovered/covered/percent
    - optional uncovered bin names from detailed tables

    It does NOT assume FIFO-specific names.
    """

    # Summary is the source of truth for what is uncovered.
    # Detailed tables are used only for bin names.
    summary_content = _extract_xcrg_section(
        content,
        "CoverGroups Summary",
        "CoverPoint Tables"
    )

    if not summary_content:
        summary_content = content

    detailed_bins = _parse_detailed_bins_by_table_tag(content)

    holes = []

    current_covergroup = ""
    current_instance = ""
    current_instance_index = 0
    current_kind = None
    in_object_table = False

    # Needed because Vivado may print the same InstName for multiple instances.
    instance_occurrences = defaultdict(int)

    for raw_line in summary_content.splitlines():
        line = raw_line.rstrip("\n")

        # New covergroup
        cg_match = re.match(r"\s*Cover Group Details\s*:\s*(.+?)\s*$", line)
        if cg_match:
            current_covergroup = _clean_ws(cg_match.group(1))
            current_instance = ""
            current_instance_index = 0
            current_kind = None
            in_object_table = False
            continue

        # Instance details block
        inst_match = re.match(
            r"\s*Instance\s+(.+?)\s+(Cover Point Details|Cross Cover Point Details)\s*$",
            line,
            re.IGNORECASE,
        )

        if inst_match:
            current_instance = _clean_ws(inst_match.group(1))
            details_type = inst_match.group(2).lower()

            if details_type.startswith("cover point"):
                current_kind = "coverpoint"

                # A Cover Point Details block marks a new instance occurrence.
                instance_occurrences[(current_covergroup, current_instance)] += 1
                current_instance_index = instance_occurrences[
                    (current_covergroup, current_instance)
                ]

            else:
                current_kind = "cross"

                # Cross details belong to the most recent coverpoint instance block.
                if instance_occurrences[(current_covergroup, current_instance)] == 0:
                    instance_occurrences[(current_covergroup, current_instance)] = 1

                current_instance_index = instance_occurrences[
                    (current_covergroup, current_instance)
                ]

            in_object_table = True
            continue

        if not in_object_table or current_kind not in {"coverpoint", "cross"}:
            continue

        stripped = line.strip()

        if (
            not stripped
            or stripped.startswith("Name")
            or stripped.startswith("TableTag")
            or stripped.startswith("Instance ")
            or stripped.startswith("Cover Group Details")
            or "::::" in stripped
        ):
            continue

        cells = _split_csv_line(raw_line)

        # Expected row:
        # Name, TableTag, Expected, Uncovered, Covered, Percent, ...
        if len(cells) < 6:
            continue

        object_name = cells[0].strip()
        table_tag = _normalize_tag(cells[1])

        if not re.match(r"^[A-Za-z_]\w*$", object_name):
            continue

        expected = _to_int(cells[2])
        uncovered = _to_int(cells[3])
        covered = _to_int(cells[4])
        percent = _to_float(cells[5])

        if expected is None or uncovered is None:
            continue

        if uncovered <= 0:
            continue

        bins = []
        queue_for_tag = detailed_bins.get((current_kind, table_tag))

        if queue_for_tag:
            bins = queue_for_tag.popleft() or []

        hole = {
            "kind": current_kind,
            "name": object_name,
            "covergroup": current_covergroup,
            "covergroup_short": _short_covergroup_name(current_covergroup),
            "instance": current_instance,
            "instance_index": current_instance_index,
            "table_tag": table_tag,
            "expected": expected,
            "uncovered": uncovered,
            "covered": covered,
            "percent": percent,
            "bins": bins,
        }

        hole["key"] = (
            f"{hole.get('covergroup_short')}::"
            f"{hole.get('instance_index')}::"
            f"{hole.get('kind')}::"
            f"{hole.get('name')}"
        )

        hole["display"] = format_hole_for_ui(hole)
        hole["description"] = format_hole_for_analyzer(hole)

        holes.append(hole)

    return holes


# ============================================================
# ----------- PUBLIC STRUCTURED PARSER ------------------------
# ============================================================

def parse_xcrg_functional_coverage(path: str) -> dict:
    """
    Generic parser for Vivado/XSim xcrg text functional coverage reports.
    """

    if not path:
        return {
            "status": "ERROR",
            "error": "empty_report_path",
            "summary": {},
            "holes": [],
        }

    if not os.path.exists(path):
        return {
            "status": "ERROR",
            "error": f"coverage_report_not_found: {path}",
            "summary": {},
            "holes": [],
        }

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "summary": {},
            "holes": [],
        }

    summary = _extract_total_summary(content)
    holes = _parse_covergroups_summary(content)

    return {
        "status": "OK",
        "error": "",
        "summary": summary,
        "holes": holes,
    }


# ============================================================
# ----------- FORMATTING --------------------------------------
# ==============================================================

def format_hole_for_ui(hole: dict) -> str:
    """
    Compact text shown in the UI.
    Keeps only the information needed by the user.
    """

    cg = hole.get("covergroup_short", "unknown_cg")
    idx = hole.get("instance_index", 0)
    kind = hole.get("kind", "item")
    name = hole.get("name", "unknown")

    expected = hole.get("expected", 0) or 0
    uncovered = hole.get("uncovered", 0) or 0
    bins = hole.get("bins") or []

    source = f"{cg}#{idx}" if idx else cg

    if kind == "coverpoint":
        kind_label = "CP"
    elif kind == "cross":
        kind_label = "Cross"
    else:
        kind_label = kind

    if bins and len(bins) <= 2:
        missing = ", ".join(bins)
    elif bins and len(bins) > 2:
        missing = f"{uncovered}/{expected} bins"
    else:
        missing = f"{uncovered}/{expected} bins"

    return f"{source} | {kind_label} {name} | missing: {missing}"

def format_hole_for_analyzer(hole: dict) -> str:
    """
    Complete technical text passed to the Analyzer.
    This is intentionally more detailed than UI display.
    """

    cg = hole.get("covergroup_short", "unknown_cg")
    full_cg = hole.get("covergroup", "")
    inst = hole.get("instance", "")
    idx = hole.get("instance_index", 0)

    bins = hole.get("bins") or []

    if bins:
        detail = "bins not covered: " + ", ".join(bins)
    else:
        detail = f"{hole.get('uncovered')} bins not covered"

    return (
        f"- {hole.get('kind')} '{hole.get('name')}' "
        f"[covergroup={cg}, full_covergroup={full_cg}, "
        f"instance={inst}#{idx}, table_tag={hole.get('table_tag')}, "
        f"expected={hole.get('expected')}, uncovered={hole.get('uncovered')}, "
        f"covered={hole.get('covered')}, percent={hole.get('percent')}%]: "
        f"{detail}"
    )


# ============================================================
# ----------- BACKWARD COMPATIBILITY FUNCTIONS ----------------
# ==============================================================

def build_coverage_holes_list(path: str) -> list[dict]:
    """
    Function to be used by Analyzer.build_holes_list().
    Returns structured holes with both:
    - display: short UI text
    - description: full Analyzer text
    """

    parsed = parse_xcrg_functional_coverage(path)

    if parsed["status"] != "OK":
        return []

    holes = parsed.get("holes", [])

    result = []

    for idx, hole in enumerate(holes):
        item = dict(hole)
        item["id"] = idx + 1
        item["display"] = hole.get("display", format_hole_for_ui(hole))
        item["description"] = hole.get("description", format_hole_for_analyzer(hole))
        result.append(item)

    return result


def extract_coverage_holes(path: str) -> str:
    """
    Old API used by current code.
    Returns text lines starting with '-', but generated from structured holes.
    """

    parsed = parse_xcrg_functional_coverage(path)

    if parsed["status"] != "OK":
        return f"ERROR: {parsed.get('error', 'coverage_parse_failed')}"

    holes = parsed.get("holes", [])

    if not holes:
        return "No obvious coverage holes found in text report."

    return "\n".join(format_hole_for_analyzer(hole) for hole in holes)


def extract_coverage_percent(path: str) -> float:
    """
    Returns global Coverage Score from Total Summary.
    """

    parsed = parse_xcrg_functional_coverage(path)

    if parsed["status"] != "OK":
        return 0.0

    return float(parsed.get("summary", {}).get("coverage_score", 0.0) or 0.0)


def extract_number_of_tests(path: str) -> int:
    """
    Useful for checking whether the report includes one test or multiple tests.
    """

    parsed = parse_xcrg_functional_coverage(path)

    if parsed["status"] != "OK":
        return 0

    return int(parsed.get("summary", {}).get("number_of_tests", 0) or 0)

# ============================================================
# ----------- SIMULATION LOG FILTERING ------------------------
# ============================================================

def filter_log_for_hole(sim_log: str, hole_description: str, max_lines: int = 120) -> str:
    """
    Extracts relevant simulation log lines for the selected coverage hole.

    The function is intentionally generic:
    - it does not assume FIFO-specific signal names;
    - it extracts useful identifiers from the selected coverage hole;
    - it searches the simulation log for related terms;
    - if no match is found, it returns a compact fallback.
    """

    if not sim_log:
        return "No simulation log available."

    if not hole_description:
        return sim_log[-8000:]

    # Extract terms from the coverage hole description.
    terms = set()

    # Terms inside quotes: coverpoint/cross names, bin names if present.
    quoted_terms = re.findall(r"'([^']+)'", hole_description)
    for term in quoted_terms:
        if term:
            terms.add(term.lower())

    # Metadata fields from the technical description.
    metadata_matches = re.findall(
        r"(?:covergroup|instance|table_tag)\s*=\s*([^,\]]+)",
        hole_description,
        re.IGNORECASE,
    )

    for term in metadata_matches:
        cleaned = term.strip().lower()
        if cleaned:
            terms.add(cleaned)

    # General identifiers from the text.
    identifiers = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", hole_description)

    ignored = {
        "coverpoint", "cross", "covergroup", "full_covergroup",
        "instance", "table_tag", "expected", "uncovered",
        "covered", "percent", "bins", "not", "covered",
        "missing", "bin", "active"
    }

    for ident in identifiers:
        ident_l = ident.lower()
        if len(ident_l) >= 3 and ident_l not in ignored:
            terms.add(ident_l)

    # Prefer meaningful terms and avoid too many generic matches.
    terms = {
        term for term in terms
        if len(term) >= 3
    }

    log_lines = sim_log.splitlines()
    matched_indices = set()

    for idx, line in enumerate(log_lines):
        line_l = line.lower()

        if any(term in line_l for term in terms):
            start = max(0, idx - 3)
            end = min(len(log_lines), idx + 4)

            for i in range(start, end):
                matched_indices.add(i)

    if matched_indices:
        selected_lines = [
            log_lines[i]
            for i in sorted(matched_indices)
        ]

        if len(selected_lines) > max_lines:
            selected_lines = selected_lines[:max_lines]
            selected_lines.append("[INFO] Log filter truncated because too many matching lines were found.")

        return "\n".join(selected_lines)

    # Fallback: keep important UVM / warning / error lines.
    important_lines = [
        line for line in log_lines
        if any(marker in line.lower() for marker in [
            "uvm_info",
            "uvm_warning",
            "uvm_error",
            "uvm_fatal",
            "error",
            "warning",
            "coverage",
            "subscriber",
            "monitor",
            "driver",
            "scoreboard",
        ])
    ]

    if important_lines:
        if len(important_lines) > max_lines:
            important_lines = important_lines[-max_lines:]

        return "\n".join(important_lines)

    # Last fallback: return the tail of the log.
    return "\n".join(log_lines[-max_lines:])