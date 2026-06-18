DYNAMIC_RAG_QUERY = """Analyze the verification project context for the selected coverage hole: '{query_context}'.

Extract the information that is useful for understanding and fixing this coverage hole:
- DUT/module interface: ports, directions, bit-widths, and signal meaning;
- relevant transaction class fields, using their exact names;
- relevant driver, monitor, subscriber, scoreboard, sequence, and test behavior;
- existing covergroups, coverpoints, bins, crosses, and sampling conditions;
- reset behavior and any protocol/state constraints that affect valid stimulus generation;
- existing sequences/tests that may already target or miss this scenario;
- run script information, including which tests are currently executed.

Focus on exact names from the project code. 
Do not assume signal names. If a detail is not present in the context, state that it was not found.
Return the answer in concise structured bullet points.
"""

STATIC_RAG_QUERY = """Provide concise UVM/SystemVerilog guidelines useful for analyzing and fixing functional coverage holes in a UVM testbench.

Include rules about:
- defining and sampling covergroups inside uvm_subscriber#(transaction);
- writing valid coverpoints, bins, iff conditions, and cross coverage;
- generating directed UVM sequences and tests for uncovered bins;
- keeping stimulus valid with respect to DUT state, reset, full/empty conditions, and protocol constraints;
- using exact transaction fields and avoiding undeclared signals;
- connecting new tests and sequences correctly through the UVM factory;
- updating Vivado/XSim run scripts to execute additional tests;
- common mistakes in generated SystemVerilog/UVM code, especially syntax errors, missing semicolons, invalid randomize-with blocks, missing factory registration, and wrong hierarchy paths;
- Vivado/XSim-compatible SystemVerilog syntax.

Return practical rules, not a general tutorial.
"""