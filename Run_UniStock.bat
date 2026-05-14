@echo off
echo Starting UniStock Inventory System...
echo.
echo [1/2] Launching browser...
start http://127.0.0.1:8000
echo.
echo [2/2] Starting server...
echo (Keep this window open while using the app)
python manage.py runserver
pause
