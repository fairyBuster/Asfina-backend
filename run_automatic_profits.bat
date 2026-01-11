@echo off
echo Starting Automatic Profit Processing...
echo =====================================

cd /d "C:\API-DJANGO"

echo Current directory: %CD%
echo Current time: %DATE% %TIME%
echo.

echo Running automatic profit processing...
python manage.py process_automatic_profits

echo.
echo Process completed at: %DATE% %TIME%
echo =====================================

pause