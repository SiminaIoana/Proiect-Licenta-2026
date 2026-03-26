from typing import TypedDict

# agent state class
class AgentState(TypedDict):
    dut_specs: str
    dynamic_docs_path: str
    uvm_rules: str
    static_docs_path: str
    action_plan: str
    generated_code: str
    iterations: int
    compilation_error: str
    coverage_holes: str
    status: str
    target_coverage: float
    iteration_tokens: int
   