# ==========================================
# prompts.py
# ==========================================

GENERATOR_SYSTEM_PROMPT = "You are an Expert SystemVerilog and UVM Developer."

# Promptul pentru adăugarea de secvențe/teste noi pentru coverage holes
GENERATOR_FIX_HOLE_PROMPT = """The Analyzer has identified a coverage hole and created an action plan.

ANALYZER'S ACTION PLAN:
{plan}

CURRENT ENVIRONMENT AND RTL:
{target_code}

DUT SPECIFICATIONS:
{specs}

YOUR TASK:
Based on the Action Plan, generate ONLY the NEW code that needs to be appended to the target files (e.g., the new sequence class and the new test class).

CRITICAL INSTRUCTIONS:
1. DO NOT rewrite or output the existing classes or existing code from the provided files, unless you are using the SEARCH/REPLACE format.
2. ONLY output the new classes that need to be added.
3. For the new test class, ensure you properly instantiate the sequence and start it using the correct hierarchy from the current environment (e.g., seq.start(environment_h.agent_h.sequencer_h);).
4. Enclose the code for each file in its own standard markdown block (```systemverilog ... ```).
5. The VERY FIRST LINE inside EACH markdown block MUST be a comment with the exact file name you are targeting:
   // FILE: <name_of_the_file.ext>

CRITICAL OUTPUT FORMAT FOR MODIFICATIONS:
If you need to MODIFY an existing line (like changing the test name in top.sv), you MUST use this exact format:
<<<< SEARCH
(exact old code here)
==== REPLACE
(new modified code here)
>>>>

If you are just ADDING a completely new class, just output the class code normally inside the markdown block.
Do not write any explanations, just return the code in the correct format.
"""

# Promptul pentru repararea erorilor de compilare (Vivado errors)
GENERATOR_FIX_SYNTAX_PROMPT = """The simulation/compilation FAILED due to syntax or logical errors in the previously generated code.

VIVADO COMPILATION ERRORS:
{error}

RELEVANT PAST EXPERIENCE FOUND IN MEMORY:
{memory_section}
Review this to avoid repeating the same error!

CURRENT ENVIRONMENT AND RTL code that needs to be fixed:
{target_code}

DUT SPECIFICATIONS:
{specs}

YOUR TASK:
Based on the errors, identify which file is broken and rewrite it.
Return the ENTIRE updated code for that specific file.
Enclose the SystemVerilog code in standard markdown ```systemverilog ... ``` blocks.
The VERY FIRST LINE inside the markdown block MUST be a comment with the exact file name you are modifying, like this:
// FILE: name_of_the_file.sv

Do not write any explanations, just return the fixed code in the correct format.
"""