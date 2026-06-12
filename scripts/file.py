from pathlib import Path

from utils_files.coverage import (
    parse_xcrg_functional_coverage,
    extract_coverage_percent,
    extract_number_of_tests,
    extract_coverage_holes,
    build_coverage_holes_list,
)

# IMPORTANT:
# Fiindcă rulezi din LICENTA/scripts, urcăm un nivel la LICENTA.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

REPORT_PATH = PROJECT_ROOT / "FIFO_SIMULATION" / "SIM-FIFO" / "coverage_report_text" / "functionalCoverageReport" / "xcrg_func_cov_report.txt"

print("Report path:", REPORT_PATH)
print("Exists:", REPORT_PATH.exists())

parsed = parse_xcrg_functional_coverage(str(REPORT_PATH))

print("Parser status:", parsed.get("status"))
print("Parser error:", parsed.get("error"))
print("Summary:", parsed.get("summary"))

print("Coverage:", extract_coverage_percent(str(REPORT_PATH)))
print("Number of tests:", extract_number_of_tests(str(REPORT_PATH)))

print("\nRAW HOLES:")
print(extract_coverage_holes(str(REPORT_PATH)))

print("\nDISPLAY HOLES:")
holes = build_coverage_holes_list(str(REPORT_PATH))

for h in holes:
    print(f"{h['id']}. {h['display']}")
    print(f"   TECH: {h['description']}")