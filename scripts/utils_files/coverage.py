import os
import re
from utils_files.status import Status
from collections import defaultdict, deque

# Text helpers for parsing and formatting coverage holes from Vivado XCRG text reports.
def clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\t", " ").strip())


def normalize_tag(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def short_covergroup_name(full_name: str) -> str:
    # Extract the last part of the covergroup name, which is the most relevant.
    full_name = clean_ws(full_name)

    if "::" in full_name:
        return full_name.split("::")[-1]

    return full_name


def to_int(value, default=None):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def to_float(value, default=None):
    try:
        return float(str(value).strip())
    except Exception:
        return default


def split_csv_line(line: str) -> list[str]:
    # Values from XCRG reports often contain extra spaces.
    return [cell.strip() for cell in line.split(",")]


def extract_xcrg_section(content: str, section_name: str, next_section_name: str | None = None) -> str:
    """
    Extracts a named section from the XCRG text report.
    The function searches only for real section headers.
    """
    # XCRG sections are marked by multiple ':' characters
    header_pattern = (
        r"^\s*:{5,}\s*"
        + re.escape(section_name)
        + r"\s*:{5,}\s*$"
    )

    header_match = re.search(header_pattern, content, re.IGNORECASE | re.MULTILINE)

    if not header_match:
        return ""

    start = header_match.end()

    # If the next section is known, stop before that header
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


def extract_total_summary(content: str) -> dict:
    """
    Extracts global coverage information from the Total Summary section.
    Returns a dictionary with keys:coverage_score, total_insts_score, number_of_tests, total_covergroups, total_instances
    """
    summary_text = extract_xcrg_section(
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

    # Regex patterns to extract the required fields from the summary text
    return {
        "coverage_score": find_float(r"Coverage\s+Score\s*:\s*,?\s*([\d.]+)"),
        "total_insts_score": find_float(r"Total\s+Insts\s+Score\s*:\s*,?\s*([\d.]+)"),
        "number_of_tests": find_int(r"Number\s+of\s+Tests\s*:\s*,?\s*(\d+)"),
        "total_covergroups": find_int(r"Total\s+no\s+of\s+Cover\s+Groups\s*:\s*,?\s*(\d+)"),
        "total_instances": find_int(r"Total\s+no\s+of\s+Instances\s*:\s*,?\s*(\d+)"),
    }


def extract_uncovered_bins_from_table_body(body: str) -> list[str]:
    """
    Extracts uncovered bin names from a detailed Cover Point Table body.
    The function reads only the "Uncovered bins" subsection and stops when
    the next relevant subsection or table begins.
    """
    bins = []
    in_uncovered = False

    for raw_line in body.splitlines():
        line = raw_line.strip()

        # Start reading only after the "Uncovered bins" marker.
        if re.match(r"^(User\s+)?Uncovered bins\b", line, re.IGNORECASE):
            in_uncovered = True
            continue

        # Stop when the report switches to covered bins.
        if in_uncovered and re.match(r"^(User\s+)?Covered bins\b", line, re.IGNORECASE):
            break

        # Stop if a new table starts before the current subsection ends.
        if in_uncovered and re.match(
            r"^(Cross\s+)?Cover Point Table\s+for Inst\b",
            line,
            re.IGNORECASE,
        ):
            break

        if not in_uncovered:
            continue

        cells = split_csv_line(raw_line)

        if len(cells) < 2:
            continue

        bin_name = cells[0].strip()
        hit_count = to_int(cells[1], default=None)

        if not bin_name or bin_name.lower() == "name":
            continue

        # Uncovered bins are appended if their hit count is zero or missing.
        if hit_count == 0:
            bins.append(bin_name)

    # Remove duplicates
    return list(dict.fromkeys(bins))


def parse_detailed_bins_by_table_tag(content: str) -> dict:
    """
    Parses detailed Cover Point Table sections and groups uncovered bins by table tag.
    The CoverGroups Summary identifies the uncovered objects, while detailed
    tables may provide the actual missing bin names.
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
        table_tag = normalize_tag(match.group("table_tag"))
        body = match.group("body")

        # Cross tables and coverpoint tables are stored separately.
        kind = "cross" if table_type.lower().startswith("cross") else "coverpoint"
        bins = extract_uncovered_bins_from_table_body(body)

        # Tables with the same tag are stored in a queue.
        detailed[(kind, table_tag)].append(bins)

    return detailed


def parse_covergroups_summary(content: str) -> list[dict]:
    """
    Extracts structured coverage holes from the CoverGroups Summary section.
    Each uncovered coverpoint or cross is converted into a dictionary.
    """
    # Summary is the source of truth for what is uncovered.
    summary_content = extract_xcrg_section(
        content,
        "CoverGroups Summary",
        "CoverPoint Tables"
    )

    if not summary_content:
        summary_content = content

    # Each coverpoint and cross are stored in a specific table
    detailed_bins = parse_detailed_bins_by_table_tag(content)
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

        # Satrt of a new covergroup
        cg_match = re.match(r"\s*Cover Group Details\s*:\s*(.+?)\s*$", line)
        if cg_match:
            current_covergroup = clean_ws(cg_match.group(1))
            current_instance = ""
            current_instance_index = 0
            current_kind = None
            in_object_table = False
            continue

        # Detect if it a coverpoint or cross table and extract the instance name.
        inst_match = re.match(
            r"\s*Instance\s+(.+?)\s+(Cover Point Details|Cross Cover Point Details)\s*$",
            line,
            re.IGNORECASE,
        )

        if inst_match:
            current_instance = clean_ws(inst_match.group(1))
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

        # Ignore lines until a valid coverpoint/cross table is active
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

        cells = split_csv_line(raw_line)

        # Ignore rows that do not start with a valid identifier.
        if len(cells) < 6:
            continue

        object_name = cells[0].strip()
        table_tag = normalize_tag(cells[1])

        if not re.match(r"^[A-Za-z_]\w*$", object_name):
            continue

        expected = to_int(cells[2])
        uncovered = to_int(cells[3])
        covered = to_int(cells[4])
        percent = to_float(cells[5])

        if expected is None or uncovered is None:
            continue

        # Ignore the covered bins
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
            "covergroup_short": short_covergroup_name(current_covergroup),
            "instance": current_instance,
            "instance_index": current_instance_index,
            "table_tag": table_tag,
            "expected": expected,
            "uncovered": uncovered,
            "covered": covered,
            "percent": percent,
            "bins": bins,
        }

        # The form of items in interface
        hole["key"] = (
            f"{hole.get('covergroup_short')}::"
            f"{hole.get('instance_index')}::"
            f"{hole.get('kind')}::"
            f"{hole.get('name')}"
        )

        # Every format is saved in the hole dictionary for later use
        hole["display"] = format_hole_for_ui(hole)
        hole["description"] = format_hole_for_analyzer(hole)

        holes.append(hole)

    return holes


def parse_xcrg_functional_coverage(path: str) -> dict:
    """
    Parses a Vivado/XSim XCRG text functional coverage report.
    Returns a dictionary with parser status, global coverage summary and
    structured uncovered coverage items.
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

    summary = extract_total_summary(content)
    holes = parse_covergroups_summary(content)

    return {
        "status": "OK",
        "error": "",
        "summary": summary,
        "holes": holes,
    }


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

    # Show explicit bin names only when the list is short enough for the UI
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
    This is more detailed than UI display.
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


def build_coverage_holes_list(path: str) -> list[dict]:
    """
    Builds the structured holes list used by Analyzer.build_holes_list().
    The returned items contain both a compact UI display text and a detailed description.
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
    Returns uncovered coverage holes as text.
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
    For checking whether the report includes one test or multiple tests.
    """
    parsed = parse_xcrg_functional_coverage(path)

    if parsed["status"] != "OK":
        return 0

    return int(parsed.get("summary", {}).get("number_of_tests", 0) or 0)


def filter_log_for_hole(sim_log: str, hole_description: str, max_lines: int = 120) -> str:
    """
    Extracts relevant simulation log lines for the selected coverage hole.
    The function is intentionally generic:
    - it does not assume specific signal names;
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

    # Terms inside quotes are coverpoint/cross names, bin names if present.
    quoted_terms = re.findall(r"'([^']+)'", hole_description)
    for term in quoted_terms:
        if term:
            terms.add(term.lower())

    # Data fields from the technical description.
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

    # Avoid too many generic matches.
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

    # Keep important UVM warning or error lines.
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

    # Return the tail of the log.
    return "\n".join(log_lines[-max_lines:])


def validate_coverage_report(report_file_path: str):
    """
    Validates the generated coverage report before Analyzer parsing.
    The function checks that the report exists, is not empty and contains a
    global coverage score.
    """
    if not os.path.exists(report_file_path):
        return (
            Status.FAILED,
            "Coverage Report Missing",
            "N/A",
            "Vivado ran successfully, but coverage report was not generated."
        )

    if os.path.getsize(report_file_path) == 0:
        return (
            Status.FAILED,
            "Coverage Report Empty",
            "N/A",
            "Coverage report exists but is empty."
        )

    coverage_val = extract_coverage_percent(report_file_path)

    if coverage_val is None or coverage_val == "N/A":
        return (
            Status.FAILED,
            "Coverage Parse Error",
            "N/A",
            "Coverage report exists, but coverage percentage could not be extracted."
        )

    return Status.SUCCESS, "None", coverage_val, ""

