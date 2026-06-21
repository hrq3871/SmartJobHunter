"""Apply all JS changes for nav restructure. Uses exact string replacement."""
path = 'D:/ccworkplace/Smarthunter/templates/index.html'
text = open(path, 'r', encoding='utf-8').read()
changes = 0

# 1. Update TITLES/DESCS
old = "const TITLES={tasks:'简历与巡检',strategy:'公司与策略'};\nconst DESCS={tasks:'上传简历、查看巡检报告、管理飞书配置',strategy:'管理公司配置和抓取策略健康状态'};"
new = "const TITLES={tasks:'简历与巡检',health:'策略健康',strategy:'公司配置',feishu:'飞书推送'};\nconst DESCS={tasks:'上传简历、查看巡检报告、启动针对性巡检',health:'查看和管理公司抓取策略健康状态',strategy:'管理公司链接和抓取策略配置',feishu:'配置飞书知识库和多维表格推送'};"
if old in text:
    text = text.replace(old, new)
    changes += 1
    print('1. TITLES/DESCS updated')
else:
    print('1. TITLES/DESCS NOT FOUND')

# 2. Update health badge to use #healthBadge
old = "$('#btnHealthCheck').querySelector('span').textContent=`策略健康 (${h.summary.total})`"
new = "const b=$('#healthBadge');if(b)b.textContent=h.summary.total"
if old in text:
    text = text.replace(old, new)
    changes += 1
    print('2. Health badge updated')
else:
    print('2. Health badge NOT FOUND')

# 3. Remove old button event listeners
old = """// ── Run inspection from sidebar ──
$('#btnRunInspect').addEventListener('click',async()=>{
  if(_currentTab!=='tasks'){switchTab('tasks');setTimeout(()=>runInspect(),300)}else runInspect();
});
$('#btnHealthCheck').addEventListener('click',()=>{switchTab('strategy');setTimeout(()=>{_strategySubTab='health';renderStrategyContent()},200)});

async function runInspect(){"""
new = """// ── Run inspection ──
async function runInspect(){"""
if old in text:
    text = text.replace(old, new)
    changes += 1
    print('3. Button listeners removed')
else:
    print('3. Button listeners NOT FOUND')

# 4. Add health and feishu renderers at the end before Init
marker = "\n// ── Init ──\nswitchTab('tasks');"
if marker in text:
    new_renderers = """
// Tab: 策略健康 (standalone)
renderers.health=async()=>{
  const h=await api('/api/health');_healthData=h;updateHealthBadge();
  $('#topbarActions').innerHTML='<button class=\"btn btn-outline btn-sm\" onclick=\"renderers.health()\">刷新</button>';
  _strategySubTab='health';renderStrategyContent();
};

// Tab: 飞书推送 (standalone)
renderers.feishu=async()=>{
  const cfg=await api('/api/config');const fconf=cfg.feishu||{};
  $('#topbarActions').innerHTML='';
  var h='<div class=\"card\"><div class=\"card-header\"><h3>飞书推送配置</h3><p class=\"text-sm text-muted\">配置飞书应用凭证，开启后巡检报告自动推送到飞书知识库和多维表格。</p></div>';
  h+='<label class=\"toggle\" style=\"margin-bottom:16px\"><input type=\"checkbox\" '+ (fconf.enabled?\"checked\":\"\") +' onchange=\"toggleFs(this.checked)\"><div class=\"toggle-track\"></div><span>'+ (fconf.enabled?\"推送已开启\":\"推送已关闭\") +'</span></label>';
  h+='<div style=\"display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:600px\">';
  var fl=[['App ID','fAppId',fconf.app_id||''],['App Secret','fAppSecret',fconf.app_secret||''],['Wiki Token','fWiki',fconf.wiki_node_token||''],['Bitable Token','fBitable',fconf.bitable_token||''],['Table ID','fTableId',fconf.bitable_table_id||'']];
  for(var i=0;i<fl.length;i++){var lb=fl[i][0];var fi=fl[i][1];var fv=fl[i][2];h+='<div><label class=\"form-label\">'+lb+'</label><input id=\"'+fi+'\" value=\"'+esc(fv)+'\" '+ (fi==='fAppSecret'?'type=\"password\"':'') +'></div>';}
  h+='</div><button class=\"btn btn-primary mt-3\" onclick=\"saveFeishu()\">保存</button></div>';
  document.getElementById('content').innerHTML=h;
};
"""
    text = text.replace(marker, new_renderers + marker)
    changes += 1
    print('4. Health and feishu renderers added')
else:
    print('4. Init marker NOT FOUND')

if changes == 4:
    open(path, 'w', encoding='utf-8').write(text)
    print('\nALL 4 CHANGES APPLIED SUCCESSFULLY')
else:
    print(f'\nWARNING: Only {changes}/4 changes applied')
