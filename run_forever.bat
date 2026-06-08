@echo off
cd /d %~dp0
:loop
echo [%date% %time%] 갓빈 페이퍼 트레이딩 시작
python main.py
echo [%date% %time%] 종료됨 - 10초 후 재시작...
timeout /t 10 /nobreak
goto loop
