@echo off
cd /d %~dp0

:: vivado settings
call C:\Xilinx\2025.2\Vivado\settings64.bat

:: remove old versions
if exist xsim.dir rmdir /s /q xsim.dir
if exist coverage_db rmdir /s /q coverage_db
if exist coverage_report_text rmdir /s /q coverage_report_text
if exist coverage_report_html rmdir /s /q coverage_report_html

:: compile
call xvlog -sv -L uvm "..\RTL-FIFO\dut.sv" "..\TB-FIFO\top.sv" -i "..\TB-FIFO"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

call xelab top -L uvm -timescale 1ns/1ps -s top_sim -cov_db_dir ./coverage_db
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%



:: run test_case_1
call xsim top_sim -R -testplusarg "UVM_TESTNAME=test_case_1" -cov_db_name cov_test1 > xsim_test1.log 2>&1
if %ERRORLEVEL% NEQ 0 echo [WARNING] test_case_1 failed!

:: run test_case_2
call xsim top_sim -R -testplusarg "UVM_TESTNAME=test_case_2" -cov_db_name cov_test2 > xsim_test2.log 2>&1
if %ERRORLEVEL% NEQ 0 echo [WARNING] test_case_2 failed!


call xsim top_sim -R -testplusarg "UVM_TESTNAME=test_case_3" -cov_db_name cov_test3 > xsim_test3.log 2>&1
if %ERRORLEVEL% NEQ 0 echo [WARNING] test_case_3 failed!
:: functional coverage report 
call xcrg -dir ./coverage_db -report_format text -report_dir ./coverage_report_text
call xcrg -dir ./coverage_db -report_format html -report_dir ./coverage_report_html

