@echo off
cd /d %~dp0

::vivado settings
call C:\Xilinx\2025.2\Vivado\settings64.bat

:: remove old versions
if exist xsim.dir rmdir /s /q xsim.dir
if exist coverage_db rmdir /s /q coverage_db
if exist coverage_report_text rmdir /s /q coverage_report_text
if exist coverage_report_html rmdir /s /q coverage_report_html
:: compile
call xvlog -sv -L uvm "..\RTL-FIFO\dut.sv" "..\TB-FIFO\top.sv" -i "..\TB-FIFO"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
:: xelab for data base
call xelab top -L uvm -timescale 1ns/1ps -s top_sim -cov_db_name my_cov_db -cov_db_dir ./coverage_db
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
::  run 
call xsim top_sim -R
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
:: rfunctional coverage report
call xcrg -dir ./coverage_db -db_name my_cov_db -report_format text -report_dir ./coverage_report_text

call xcrg -dir ./coverage_db -db_name my_cov_db -report_format html -report_dir ./coverage_report_html
