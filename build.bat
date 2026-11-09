@echo off
pip install -r requirements.txt
python -m PyInstaller --noconsole --onefile --uac-admin --icon icon.ico --name GenshinSkip genshin_skip.py
echo Готово: dist\GenshinSkip.exe
