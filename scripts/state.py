from typing import TypedDict

# agent state class
class AgentState(TypedDict):
    dut_specs: str
    uvm_rules: str
    action_plan: str
    generated_code: str
    iterations: int
    compilation_error: str
    coverage_holes: str
    status: str
   