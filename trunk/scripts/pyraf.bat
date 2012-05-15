@ECHO OFF
REM BFCPEOPTIONSTART
REM Advanced BAT to EXE Converter www.BatToExeConverter.com
REM BFCPEEXE=C:\Documents and Settings\Owner\Desktop\PyRAF.exe
REM BFCPEICON=C:\tmp\pyraflogo_rgb_web.ico
REM BFCPEICONINDEX=8
REM BFCPEEMBEDDISPLAY=0
REM BFCPEEMBEDDELETE=1
REM BFCPEVERINCLUDE=1
REM BFCPEVERVERSION=1.0.0.0
REM BFCPEVERPRODUCT=PyRAF
REM BFCPEVERDESC=PyRAF for Windows
REM BFCPEVERCOMPANY=STScI
REM BFCPEVERCOPYRIGHT=See startup messages
REM BFCPEOPTIONEND
@ECHO ON
@echo off
rem - This was created via "Advanced BAT to EXE Converter v2.45"
rem - Install resulting exe in:
rem -    %USERPROFILE%\Desktop\PyRAF.exe
rem - I used the following to convert the PyRAF gif to a .ico file:
rem -    http://www.coolutils.com/online/image-converter
echo.
echo Running %0
cd %APPDATA%
echo Launching PyRAF ...
echo.
runpyraf.py
echo.
pause
