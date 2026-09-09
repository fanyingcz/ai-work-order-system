@echo off
REM ============================================================
REM 智能工单系统 一键启动（本地演示）
REM   后端 8000  (FastAPI, 含已构建前端托管: / 报修端 /worker 工人端)
REM   报修端 5173 (Vite dev, frontend/)
REM   工人端 5174 (Vite dev, worker-frontend/)
REM 关闭对应窗口即停止该服务。
REM ============================================================
cd /d "%~dp0"

REM --- 1. 后端 8000 ---
start "工单-后端8000" cmd /k ""C:\Users\73116\anaconda3\python.exe" -m uvicorn api:app --host 127.0.0.1 --port 8000"

REM --- 2. 报修端 5173 (dev) ---
cd /d "%~dp0frontend"
start "工单-报修端5173" cmd /k "node_modules\.bin\vite.cmd --port 5173"

REM --- 3. 工人端 5174 (dev) ---
cd /d "%~dp0worker-frontend"
start "工单-工人端5174" cmd /k "node_modules\.bin\vite.cmd --port 5174"

cd /d "%~dp0"

REM --- 4. 等服务起来后打开两个前端 ---
timeout /t 6 /nobreak >nul
start "" http://localhost:5173
start "" http://localhost:5174

echo.
echo 已启动: 后端8000 + 报修端5173 + 工人端5174
echo 已打开浏览器; 也可手动访问 http://127.0.0.1:8000 (构建版前端+API文档/docs)
echo 关闭对应窗口即停止服务。
pause
