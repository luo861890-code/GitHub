import sys, re
sys.stdout.reconfigure(encoding="utf-8")
src = open("app/main.py", encoding="utf-8").read()
for m in re.finditer(r'@app\.(get|post|put|delete)\("([^"]+)"', src):
    print(m.group(1).upper(), m.group(2))
