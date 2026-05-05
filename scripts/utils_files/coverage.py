import os
import re
import csv
import datetime
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage

# ==============================================================
# ------ FUNCTION FOR EXTRACTING HOLES FROM FCOV -------
# ==============================================================
def extract_coverage_holes(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return "ERROR: file_not_found"
    except Exception as e:
        return f"ERROR: {str(e)}"

    holes = {}

    def add_hole(kind: str, name: str, bins):
        key = (kind, name)

        if isinstance(bins, str):
            bins = [bins]

        if key not in holes:
            holes[key] = []

        for b in bins:
            b = str(b).strip()
            if b and b not in holes[key]:
                holes[key].append(b)

    # ------------------------------------------------------------
    # 1. Parse detailed Cover Point / Cross Cover Point tables
    # ------------------------------------------------------------
    table_pattern = re.compile(
        r'(?P<table_type>Cover Point Table|Cross Cover Point Table)\s+for Inst\s*:.*?Variable\s*:,?\s*(?P<var>[\w]+)(?P<body>.*?)(?=(?:Cover Point Table|Cross Cover Point Table)\s+for Inst|$)',
        re.DOTALL
    )

    for match in table_pattern.finditer(content):
        table_type = match.group("table_type")
        variable = match.group("var").strip()
        block = match.group("body")

        kind = "cross" if table_type.startswith("Cross") else "coverpoint"

        uncov_match = re.search(
            r'(?:Uncovered bins|User Uncovered bins)\s*\n(.*?)(?:Covered bins|User Covered bins|$)',
            block,
            re.DOTALL
        )

        if not uncov_match:
            continue

        uncov_section = uncov_match.group(1)

        bin_names = re.findall(
            r'^\s*([\w\[\]]+)\s*,\s*0\s*,',
            uncov_section,
            re.MULTILINE
        )

        # Remove duplicates while preserving order
        bin_names = list(dict.fromkeys(bin_names))

        if bin_names:
            add_hole(kind, variable, bin_names)

    # ------------------------------------------------------------
    # 2. Parse Cover Point Details summary as fallback
    # ------------------------------------------------------------
    cp_summary_match = re.search(
        r'Instance\s+.*?Cover Point Details\s*(.*?)\n\s*Instance\s+.*?Cross Cover Point Details',
        content,
        re.DOTALL
    )

    if cp_summary_match:
        cp_summary = cp_summary_match.group(1)

        for line in cp_summary.splitlines():
            line = line.strip()
            if not line or line.startswith("Name") or line.startswith("TableTag"):
                continue

            # Example:
            # re_cp ,tabletag,2 ,1 ,1 ,50 ...
            m = re.match(
                r'^(\w+)\s*,.*?,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)',
                line
            )

            if not m:
                continue

            name = m.group(1)
            uncovered = int(m.group(3))

            if uncovered > 0 and ("coverpoint", name) not in holes:
                add_hole("coverpoint", name, f"{uncovered} bins not covered")

    # ------------------------------------------------------------
    # 3. Parse Cross Cover Point Details summary as fallback
    # ------------------------------------------------------------
    cross_summary_match = re.search(
        r'Instance\s+.*?Cross Cover Point Details\s*(.*?)(?=::::::::::::::::|CoverPoint Tables|$)',
        content,
        re.DOTALL
    )

    if cross_summary_match:
        cross_summary = cross_summary_match.group(1)

        for line in cross_summary.splitlines():
            line = line.strip()
            if not line or line.startswith("Name") or line.startswith("TableTag"):
                continue

            # Example:
            # read_protocol_cross ,tabletag,2 ,2 ,0 ,0 ...
            m = re.match(
                r'^(\w+)\s*,.*?,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)',
                line
            )

            if not m:
                continue

            name = m.group(1)
            uncovered = int(m.group(3))

            if uncovered > 0 and ("cross", name) not in holes:
                add_hole("cross", name, f"{uncovered} bins not covered")

    if not holes:
        return "No obvious coverage holes found in text report."

    output = []

    for (kind, name), bins in holes.items():
        if len(bins) == 1 and "bins not covered" in bins[0]:
            output.append(f"- {kind} '{name}': {bins[0]}")
        else:
            output.append(f"- {kind} '{name}': bins not covered: {', '.join(bins)}")

    return "\n".join(output)

# ==============================================================
# ------ FUNCTION FOR EXTRACTING PERCENTAGE FROM FCOV -------
# ==============================================================

def extract_coverage_percent(path: str) -> float:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'Coverage Score\s*:,?\s*([\d.]+)', content)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return 0.0
    

def filter_log_for_hole(sim_log: str, hole_description: str) -> str:
    if not sim_log or not hole_description:
        return "No log available."

    stop_words = {
        "not", "covered", "bin", "bins", "the", "a", "is", "in",
        "and", "or", "of", "coverpoint", "missed", "cov"
    }

    cp_match = re.search(r"coverpoint '(\w+)'", hole_description)
    cp_name = cp_match.group(1) if cp_match else ""

    raw_keywords = hole_description.lower().replace(":", " ").replace("'", " ").replace(",", " ").split()
    keywords = [kw for kw in raw_keywords if len(kw) > 2 and kw not in stop_words]
    if cp_name and cp_name not in keywords:
        keywords.append(cp_name.lower())

    # Parsează log-ul pe blocuri per test (format nou: [xsim_test1] STATUS=...)
    test_blocks = re.split(r'(?=\[xsim_test)', sim_log)
    
    relevant_parts = []
    for block in test_blocks:
        if not block.strip():
            continue

        # Extrage status-ul testului
        status_match = re.search(r'STATUS=(\w+)', block)
        status = status_match.group(1) if status_match else "UNKNOWN"
        test_match = re.search(r'\[(xsim_test\w+)\]', block)
        test_name = test_match.group(1) if test_match else "unknown"

        # Un test FAILED nu a salvat coverage → nu e relevant pentru hole-ul de coverage
        # Îl menționăm doar ca informație, fără să îl analizăm ca root cause
        if status == "FAILED":
            relevant_parts.append(
                f"[{test_name}] FAILED (coverage data NOT saved for this test - ignore for coverage analysis)"
            )
            continue

        # Pentru teste PASSED, caută linii relevante pentru hole
        lines = block.split("\n")
        hole_lines = []
        for line in lines:
            line_lower = line.lower()
            if any(kw in line_lower for kw in keywords):
                hole_lines.append(line.strip())

        if hole_lines:
            relevant_parts.append(f"[{test_name}] Relevant entries:\n" + "\n".join(f"  >> {l}" for l in hole_lines))

    if not relevant_parts:
        return (
            "No direct log entries found for this specific hole. "
            "The hole exists due to missing stimulus in the PASSED tests."
        )

    return "\n\n".join(relevant_parts)
