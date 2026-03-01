@echo off



:: launch vivado

call C:\Xilinx\2025.2\Vivado\settings64.bat



:: delete last versions

rmdir /s /q xsim.dir 2>NUL

rmdir /s /q coverage_db 2>NUL

rmdir /s /q coverage_report 2>NUL



:: compile

call xvlog -sv -L uvm ..\RTL-FIFO\dut.sv ..\TB-FIFO\top.sv -i ..\TB-FIFO



:: coverage prepared

call xelab top -L uvm -timescale 1ns/1ps -s top_sim -cov_db_name my_cov_db -cov_db_dir ./coverage_db



:: simulation

call xsim top_sim -R



:: coverage report

call xcrg -dir ./coverage_db -db_name my_cov_db -report_format html -report_dir ./coverage_report



pause