# ==========================================
# generator_prompt.py
# ==========================================

GENERATOR_SYSTEM_PROMPT = "You are an Expert SystemVerilog, UVM, and Vivado simulation-script Developer."

GENERATOR_FIX_HOLE_PROMPT = """The Analyzer has identified a coverage hole and created an action plan.

ANALYZER'S ACTION PLAN:
{plan}

CURRENT ENVIRONMENT, RTL, AND RUN SCRIPT:
{target_code}

DUT SPECIFICATIONS:
{specs}

PREVIOUS REJECTED OR FAILED SOLUTIONS:
{rejected_memory}

Avoid repeating rejected code patterns, syntax mistakes, wrong file modifications, or user-disapproved strategies.

YOUR TASK:
Generate ONLY new code that can be safely appended by the injector.

VERY IMPORTANT ARCHITECTURAL RULE:
The injector can only:
- append new SystemVerilog classes before the final `endif
- insert new MakeSVfile.bat commands before the coverage report section

Therefore:
- Do NOT generate partial code fragments that must be inserted inside an existing task/function/class.
- Do NOT ask to modify the inside of an existing sequence body.
- If the Analyzer's plan requires modifying an existing task, instead create a NEW sequence class that implements the corrected behavior.
- If you create a NEW sequence class, you MUST also create a NEW test class that runs it.
- If you create a NEW test class, you MUST also output a MakeSVfile.bat block that runs that exact test.

STYLE RULE:
Prefer the simplest maintainable solution.
If one directed sequence and one test can cover the hole, do not create multiple duplicated sequences/tests.

OUTPUT REQUIREMENTS:
1. Return ONLY markdown code blocks. No explanations.
2. Each modified file must be in its OWN markdown code block.
3. The first line inside EACH code block MUST be:
   // FILE: exact_filename.ext
4. Use:
   - ```systemverilog for .sv files
   - ```bat for MakeSVfile.bat

SYSTEMVERILOG RULES:
- Output complete classes only, not floating statements.
- Do NOT output code fragments intended to be inserted inside an existing method.
- Do NOT place constraints outside a class.
- Do NOT append constraints after endclass.
- Do NOT modify transaction.sv unless the Analyzer explicitly says it is absolutely required.
- Prefer inline constraints inside randomize-with blocks.
- If targeting a value range, use inline randomization inside a sequence:
  trans.randomize with {{
      data_in inside {{[LOW:HIGH]}};
  }};
- Always call start_item(trans) before randomize and finish_item(trans) after randomize.
- The macro `uvm_info` MUST have exactly 3 arguments:
  `uvm_info("TAG", "message", UVM_LEVEL)
- Do NOT add a fourth argument to `uvm_info`.

PLAN COMPLIANCE RULE:
- Follow the Analyzer's goal, but respect the injector limitation above.
- If the plan says to modify an existing sequence internally, create a new sequence class that reproduces the needed behavior safely.
- Do NOT output partial internal edits.
- Do NOT create unrelated tests or unrelated files.
- The generated test name must exactly match the UVM_TESTNAME used in MakeSVfile.bat.

RUN SCRIPT / VIVADO RULES:
- The project uses Vivado, NOT ModelSim/Questa.
- NEVER use vlog.
- NEVER use vsim.
- Use only Vivado-style xsim commands already present in the run script.
- Do NOT output the full MakeSVfile.bat file.
- For MakeSVfile.bat, output ONLY the new xsim command block needed to run the new test.
- The MakeSVfile.bat block MUST start with:
  // FILE: MakeSVfile.bat

The MakeSVfile.bat command block must follow this style:

call xsim top_sim -R -testplusarg "UVM_TESTNAME=<new_test_name>" -cov_db_name cov_<new_test_name> > xsim_<new_test_name>.log 2>&1
if %ERRORLEVEL% NEQ 0 echo [WARNING] <new_test_name> failed!

CRITICAL OUTPUT FORMAT:
- Do NOT use SEARCH/REPLACE markers.
- Do NOT output <<<< SEARCH, ====, REPLACE, or >>>>.
- Do NOT output full existing files.
- Do NOT output existing classes.
- Do NOT output comments like "add this inside...".
- Output only valid code blocks that can be injected directly.

EXPECTED OUTPUT WHEN CREATING A NEW SEQUENCE:
You normally need exactly these blocks:
1. sequence.sv containing the complete new sequence class
2. test.sv containing the complete new test class
3. MakeSVfile.bat containing only the new xsim command block

Return ONLY the code blocks.
"""


GENERATOR_FIX_SYNTAX_PROMPT = """The simulation/compilation failed due to errors in generated or injected code.

VIVADO COMPILATION ERRORS:
{error}

RELEVANT PAST EXPERIENCE FOUND IN MEMORY:
{memory_section}

CURRENT ENVIRONMENT, RTL, AND RUN SCRIPT:
{target_code}

DUT SPECIFICATIONS:
{specs}

YOUR TASK:
Fix only the generated code that caused the error.

VERY IMPORTANT:
The injector can only:
- append new SystemVerilog classes before the final `endif
- insert new MakeSVfile.bat commands before the coverage report section

Therefore:
- Do NOT output partial code fragments that must be inserted inside an existing task/function/class.
- Do NOT output SEARCH/REPLACE markers.
- If a previous generated class is broken, output the complete corrected class.
- If a MakeSVfile.bat command is wrong, output only the corrected xsim command block.

OUTPUT REQUIREMENTS:
1. Return ONLY markdown code blocks. No explanations.
2. Each file must be in its OWN code block.
3. The first line inside EACH code block MUST be:
   // FILE: exact_filename.ext
4. Use:
   - ```systemverilog for .sv files
   - ```bat for MakeSVfile.bat

SYSTEMVERILOG RULES:
- Do NOT place constraints outside a class.
- Do NOT append constraints after endclass.
- The macro `uvm_info` MUST have exactly 3 arguments:
  `uvm_info("TAG", "message", UVM_LEVEL)
- Do NOT add a fourth argument to `uvm_info`.

VIVADO SCRIPT RULES:
- The project uses Vivado, NOT ModelSim/Questa.
- NEVER use vlog.
- NEVER use vsim.
- Use xsim-style commands only.
- Do NOT output the full MakeSVfile.bat file.

Return ONLY the fixed code blocks.
"""