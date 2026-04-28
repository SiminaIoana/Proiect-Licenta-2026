# ==========================================
# prompts.py
# ==========================================

GENERATOR_SYSTEM_PROMPT = "You are an Expert SystemVerilog and UVM Developer."

# Promptul pentru adăugarea de secvențe/teste noi pentru coverage holes
GENERATOR_FIX_HOLE_PROMPT = """The Analyzer has identified a coverage hole and created an action plan.

ANALYZER'S ACTION PLAN:
{plan}

CURRENT ENVIRONMENT, RTL, AND RUN SCRIPT:
{target_code}

DUT SPECIFICATIONS:
{specs}

YOUR TASK:
Based on the Action Plan, generate ONLY the NEW code that needs to be appended to the target files (e.g., the new sequence class and the new test class).

CRITICAL INSTRUCTIONS:
1. DO NOT rewrite or output existing classes or existing code.
2. ONLY output the new classes that need to be added.
3. For the new test class, ensure you properly instantiate the sequence and start it using the correct hierarchy from the current environment (e.g., seq.start(environment_h.agent_h.sequencer_h);).
4. Enclose each file in its own markdown block using the correct language:
   - ```systemverilog for .sv files
   - ```bat for .bat files
5. The VERY FIRST LINE inside EACH markdown block MUST be a comment with the exact file name you are targeting:
   // FILE: <name_of_the_file.ext>


IMPORTANT SYSTEMVERILOG PLACEMENT RULES:
- Do NOT place constraints outside a class.
- Any constraint must be declared inside a SystemVerilog class.
- If using inline constraints, place them only inside randomize with { ... } blocks.
- Do NOT append constraints after endclass.
- Do NOT generate floating SystemVerilog statements outside classes/modules.
- Do NOT add constraints directly into transaction.sv unless the Analyzer explicitly says this is absolutely required.
- Prefer inline constraints inside sequence randomize-with blocks.
- If targeting a value range, use:
  trans.randomize with {
      data_in inside {[LOW:HIGH]};
  };
- Never append constraints after endclass.

RUN SCRIPT RULE:
If a new test class is created, MakeSVfile.bat must be updated to execute that exact test name.
If you are unsure how to modify MakeSVfile.bat, still output a MakeSVfile.bat block with the intended test execution change.
If you are just ADDING a completely new class, just output the class code normally inside the markdown block.
Do not write any explanations, just return the code in the correct format.

RUN / INTEGRATION FILE RULES:
If the generated code requires changes in any integration or execution file, you MUST output a separate code block for that file.

Examples of integration files:
- MakeSVfile.bat
- run scripts
- top.sv
- package/include files
For MakeSVfile.bat, if a new test class is generated, output ONLY a new command in this style:

call xsim top_sim -R -testplusarg "UVM_TESTNAME=<new_test_name>" -cov_db_name cov_<new_test_name> > xsim_<new_test_name>.log 2>&1
if %ERRORLEVEL% NEQ 0 echo [WARNING] <new_test_name> failed!

If you create a new test class, you MUST ensure that the test is actually compiled and executed.

The solution is incomplete unless the generated stimulus is reachable during simulation.

---

CRITICAL OUTPUT FORMAT:
- Do NOT use SEARCH/REPLACE markers.
- Do NOT output <<<< SEARCH, ====, REPLACE, or >>>>.
- For .sv files, output only the new class or the corrected code fragment.
- For script/integration files (e.g., MakeSVfile.bat):
  Output the exact command or block that should be added, including enough context so it can be correctly inserted.
  Do NOT output incomplete fragments.

NAMING RULE:
The test name used in MakeSVfile.bat MUST exactly match the generated test class name.
Do NOT invent file names. Use only files that exist in the provided context unless explicitly creating a new class.

"""


# Promptul pentru repararea erorilor de compilare (Vivado errors)
GENERATOR_FIX_SYNTAX_PROMPT = """The simulation/compilation FAILED due to syntax or logical errors in the previously generated code.

VIVADO COMPILATION ERRORS:
{error}

RELEVANT PAST EXPERIENCE FOUND IN MEMORY:
{memory_section}
Review this to avoid repeating the same error!

CURRENT ENVIRONMENT, RTL, AND RUN SCRIPT:
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