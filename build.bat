@echo off
pip install -r requirements.txt
python -m PyInstaller --noconsole --onefile --uac-admin --name GenshinSkip genshin_skip.py
echo Готово: dist\GenshinSkip.exe
