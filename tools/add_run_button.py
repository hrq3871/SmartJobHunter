"""Remove feishu card from tasks sidebar, add run button."""
path = 'D:/ccworkplace/Smarthunter/templates/index.html'
text = open(path, 'r', encoding='utf-8').read()

# Find and replace the feishu card with a run button
marker = "  // Feishu\n"
idx = text.find(marker)
if idx < 0:
    print('Feishu marker NOT FOUND')
    exit(1)

# Find the end of the feishu section (it ends with the closing backtick+; for the last line)
# Look for the pattern after the feishu block: '  // Right: selected resume'
end_marker = "  // Right: selected resume\n"
end = text.find(end_marker, idx)
if end < 0:
    print('Right marker NOT FOUND')
    exit(1)

run_button = "  // Run inspection\n  left+=`<button class=\"btn btn-primary\" style=\"width:100%;margin-top:8px\" onclick=\"runInspect()\">&#x25b6; 启动巡检</button>`;\n\n  // Right: selected resume\n"

text = text[:idx] + run_button + text[end + len(end_marker):]
open(path, 'w', encoding='utf-8').write(text)
print(f'OK: replaced {end-idx} chars with run button')
