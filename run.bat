@echo off
REM A 股量化交易系统启动脚本
cd /d "%~dp0"
echo 启动 A 股量化交易系统...
echo 浏览器打开 http://localhost:8501
echo 按 Ctrl+C 停止
echo.
C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m streamlit run app.py --server.port=8501
pause
