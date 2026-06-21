text = open('D:/ccworkplace/Smarthunter/templates/index.html', 'r', encoding='utf-8').read()

# Find the broken line and fix it
marker = "left+=''\x3c"
idx = text.find(marker)
if idx > 0:
    end = text.find("';", idx)
    if end < 0: end = text.find("\n", idx)
    broken = text[idx:end+2]
    print(f'BROKEN: {repr(broken[:120])}')
    # Replace with clean backtick version
    clean = 'left+=`<button class="btn btn-primary" style="width:100%;margin-top:8px" onclick="runInspect()">&#x25b6; 启动巡检</button>`;'
    text = text[:idx] + clean + text[end+2:]
    open('D:/ccworkplace/Smarthunter/templates/index.html', 'w', encoding='utf-8').write(text)
    print('FIXED')
else:
    print('NOT FOUND - looking for:', repr(marker))
