@echo off
cd /d "%~dp0"
echo Starting PT Dashboard...
start "" http://localhost:8501
py -m streamlit run dashboard.py --server.headless true
pause
