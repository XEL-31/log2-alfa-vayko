@echo off
echo Log2 Alfa Windows Fix - venv aktive + kurulum
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements_windows.txt
echo.
echo Kurulum bitti. Simdi calistir: python main.py
pause
