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

    holes = []

    # Găsește toate secțiunile "Uncovered bins" și asociază-le cu variabila
    # Împarte conținutul în blocuri per Cover Point Table
    table_pattern = re.compile(
        r'Cover (?:Point|Cross Cover Point) Table for Inst.*?Variable\s*:,?\s*(\w+)(.*?)(?=Cover (?:Point|Cross Cover Point) Table|$)',
        re.DOTALL
    )

    for match in table_pattern.finditer(content):
        variable = match.group(1)
        block = match.group(2)

        uncov_match = re.search(
            r'Uncovered bins\s*\n(.*?)(?:Covered bins|$)',
            block, re.DOTALL
        )
        if not uncov_match:
            continue

        uncov_section = uncov_match.group(1)
        bin_names = re.findall(r'^\s+([\w\[\]]+)\s+,0\s+,', uncov_section, re.MULTILINE)
        
        bin_names = list(dict.fromkeys(bin_names))

        if bin_names:
            holes.append(
                f"- coverpoint '{variable}': bins not covered: {', '.join(bin_names)}"
            )

    if not holes:
        return "No obvious coverage holes found in text report."

    return "\n".join(holes)


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
