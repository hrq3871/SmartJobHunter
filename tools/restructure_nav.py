"""Apply all sidebar/nav restructuring in one pass."""
import re

path = 'D:/ccworkplace/Smarthunter/templates/index.html'
text = open(path, 'r', encoding='utf-8').read()

# 1. Replace sidebar nav buttons
old_nav = '''      <button class="side-item active" data-tab="tasks"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg><span>简历与巡检</span></button>
      <button class="side-item" data-tab="strategy"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4M4.22 19.78l2.83-2.83m9.9-9.9l2.83-2.83"/></svg><span>公司与策略</span></button>
    </div>
    <div class="side-section">
      <div class="side-label">管理</div>
      <button class="side-item" id="btnRunInspect"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg><span>运行巡检</span></button>
      <button class="side-item" id="btnHealthCheck"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg><span>策略健康 (0)</span></button>'''

new_nav = '''      <button class="side-item active" data-tab="tasks"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg><span>简历与巡检</span></button>
      <button class="side-item" data-tab="health"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg><span>策略健康</span><span id="healthBadge" style="margin-left:auto;font-size:10px;color:var(--text-muted)">0</span></button>
    </div>
    <div class="side-section">
      <div class="side-label">管理</div>
      <button class="side-item" data-tab="strategy"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4M4.22 19.78l2.83-2.83m9.9-9.9l2.83-2.83"/></svg><span>公司配置</span></button>
      <button class="side-item" data-tab="feishu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg><span>飞书推送</span></button>'''

text = text.replace(old_nav, new_nav)

# 2. Update TITLES/DESCS
text = text.replace(
    "const TITLES={tasks:'简历与巡检',strategy:'公司与策略'};\nconst DESCS={tasks:'上传简历、查看巡检报告、管理飞书配置',strategy:'管理公司配置和抓取策略健康状态'};",
    "const TITLES={tasks:'简历与巡检',health:'策略健康',strategy:'公司配置',feishu:'飞书推送'};\nconst DESCS={tasks:'上传简历、查看巡检报告、启动针对性巡检',health:'查看和管理公司抓取策略健康状态',strategy:'管理公司链接和抓取策略配置',feishu:'配置飞书知识库和多维表格推送'};"
)

# 3. Remove _strategySubTab
text = text.replace("let _coData=[],_healthData=null,_coFilter='all',_coHealthFilter='all',_selCompanies=new Set(),_strategySubTab='companies',_tasksSelectedResume=null,_currentTab='tasks';\n",
    "let _coData=[],_healthData=null,_coFilter='all',_coHealthFilter='all',_selCompanies=new Set(),_tasksSelectedResume=null,_currentTab='tasks';\n")

# 4. Replace old button event listeners with new health badge
old_btn_listeners = '''// ── Sidebar health badge ──
async function updateHealthBadge(){
  try{const h=await api('/api/health');$('#btnHealthCheck').querySelector('span').textContent=`策略健康 (${h.summary.total})`}catch(e){}
}
updateHealthBadge();

// ── Run inspection from sidebar ──
$('#btnRunInspect').addEventListener('click',async()=>{
  if(_currentTab!=='tasks'){switchTab('tasks');setTimeout(()=>runInspect(),300)}else runInspect();
});
$('#btnHealthCheck').addEventListener('click',()=>{switchTab('strategy');setTimeout(()=>{_strategySubTab='health';renderStrategyContent()},200)});

async function runInspect(){'''

new_btn_listeners = '''// ── Sidebar health badge ──
async function updateHealthBadge(){
  try{const h=await api('/api/health');const b=$('#healthBadge');if(b)b.textContent=h.summary.total}catch(e){}
}
updateHealthBadge();

// ── Run inspection ──
async function runInspect(){'''

text = text.replace(old_btn_listeners, new_btn_listeners)

# 5. Replace feishu card in tasks sidebar with run button
old_feishu = '''  // Feishu
  left+=`<div class="card"><div class="card-header"><h3>飞书推送 <span class="tooltip-wrap" style="margin-left:4px"><button class="tooltip-trigger">?</button><div class="tooltip-box">在飞书开放平台创建企业自建应用 → App ID / App Secret → 知识库 Wiki Token → 多维表格 Bitable Token / Table ID</div></span></h3></div>`;
  left+=`<label class="toggle" style="margin-bottom:10px"><input type="checkbox" ${fconf.enabled?"checked":""} onchange="toggleFs(this.checked)"><div class="toggle-track"></div><span>${fconf.enabled?"推送已开启":"推送已关闭"}</span></label>`;
  left+='<details><summary class="text-sm" style="cursor:pointer;color:var(--text-secondary);font-weight:500">编辑凭证</summary><div style="margin-top:8px">';
  left+='<label class="form-label" style="margin-top:8px">App ID</label>'+`<input id="fsAppId" value="${esc(fconf.app_id||"")}" style="margin-bottom:8px">`;
  left+='<label class="form-label" style="margin-top:8px">App Secret</label>'+`<input id="fsAppSecret" type="password" value="${esc(fconf.app_secret||"")}" style="margin-bottom:8px">`;
  left+='<label class="form-label" style="margin-top:8px">Wiki 节点 Token</label>'+`<input id="fsWiki" value="${esc(fconf.wiki_node_token||"")}" style="margin-bottom:8px">`;
  left+='<label class="form-label" style="margin-top:8px">多维表格 Token</label>'+`<input id="fsBitable" value="${esc(fconf.bitable_token||"")}" style="margin-bottom:8px">`;
  left+='<label class="form-label" style="margin-top:8px">多维表格 ID</label>'+`<input id="fsTableId" value="${esc(fconf.bitable_table_id||"")}">`;
  left+='<button class="btn btn-primary btn-sm mt-2" onclick="saveFs()">保存配置</button></div></details></div>`;'''

new_feishu = '''  // Run inspection
  left+=`<button class="btn btn-primary" style="width:100%;margin-top:8px" onclick="runInspect()">&#x25b6; 启动巡检</button>`;'''

text = text.replace(old_feishu, new_feishu)

# 6. Replace old strategy tab section (with sub-tabs) with simplified version
old_strat = text.find("// ══════════════════════════════════════════════\n// Tab: 公司与策略")
old_strat_end = text.find("function renderCompanyGrid(companies){", old_strat)
if old_strat > 0 and old_strat_end > 0:
    new_strat = '''// ══════════════════════════════════════════════
// Tab: 公司配置 (company management)
// ══════════════════════════════════════════════
renderers.strategy=async()=>{
  const companies=await api('/api/companies');_coData=companies;
  const h=await api('/api/health');_healthData=h;updateHealthBadge();
  $('#topbarActions').innerHTML='<div class="search-box" style="width:240px"><input type="search" id="coSearch" placeholder="搜索公司..." oninput="applyCoFilters()"></div>';
  renderCompanyGrid(_sortCompanies(_coData,_coFilter));
};

function renderCompanyGrid(companies){'''
    text = text[:old_strat] + new_strat + text[old_strat_end:]

# 7. Add standalone health and feishu renderers before "function renderHealthPanel"
old_health_marker = "\n// ── Health ──\nfunction renderHealthPanel(health){"
new_renderers = '''
// ══════════════════════════════════════════════
// Tab: 策略健康 (standalone)
// ══════════════════════════════════════════════
renderers.health=async()=>{
  const h=await api('/api/health');_healthData=h;updateHealthBadge();
  $(\'#topbarActions\').innerHTML=\'<button class="btn btn-outline btn-sm" onclick="renderers.health()">刷新</button>\';
  renderHealthPanel(h);
};

// ══════════════════════════════════════════════
// Tab: 飞书推送 (standalone)
// ══════════════════════════════════════════════
renderers.feishu=async()=>{
  const cfg=await api(\'/api/config\');const fconf=cfg.feishu||{};
  $(\'#topbarActions\').innerHTML=\'\';
  let h=\'<div class="card"><div class="card-header"><h3>飞书推送配置</h3><p class="text-sm text-muted">配置飞书应用凭证，开启后巡检报告自动推送到飞书知识库和多维表格。</p></div>\';
  h+=\'<label class="toggle" style="margin-bottom:16px"><input type="checkbox" \'+ (fconf.enabled?"checked":"") +\' onchange="toggleFs(this.checked)"><div class="toggle-track"></div><span>\'+ (fconf.enabled?"推送已开启":"推送已关闭") +\'</span></label>\';
  h+=\'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:600px">\';
  var fields=[[\'App ID\',\'fAppId\',fconf.app_id||\'\'],[\'App Secret\',\'fAppSecret\',fconf.app_secret||\'\'],[\'Wiki Token\',\'fWiki\',fconf.wiki_node_token||\'\'],[\'Bitable Token\',\'fBitable\',fconf.bitable_token||\'\'],[\'Table ID\',\'fTableId\',fconf.bitable_table_id||\'\']];
  for(var i=0;i<fields.length;i++){var label=fields[i][0];var id=fields[i][1];var val=fields[i][2];
    h+=\'<div><label class="form-label">\'+label+\'</label><input id="\'+id+\'" value="\'+esc(val)+\'" \'+ (id===\'fAppSecret\'?\'type="password"\':\'\') +\'></div>\';
  }
  h+=\'</div><button class="btn btn-primary mt-3" onclick="saveFeishuSettings()">保存</button>\';
  h+=\'<div class="text-sm text-muted mt-3">在 <a href="https://open.feishu.cn" target="_blank">飞书开放平台</a> 创建应用 → 获取凭证。</div></div>\';
  document.getElementById(\'content\').innerHTML=h;
};
window.saveFeishuSettings=async()=>{await api(\'/api/config\',{method:\'PUT\',body:JSON.stringify({feishu:{app_id:$(\'#fAppId\').value.trim(),app_secret:$(\'#fAppSecret\').value.trim(),wiki_node_token:$(\'#fWiki\').value.trim(),bitable_token:$(\'#fBitable\').value.trim(),bitable_table_id:$(\'#fTableId\').value.trim()}})});toast(\'飞书配置已保存\')};

// ── Health ──
function renderHealthPanel(health){'''

text = text.replace(old_health_marker, new_renderers)

# 8. Fix renderHealthPanel to use #content instead of #strategyContent
text = text.replace("const sc=document.getElementById('strategyContent');if(!sc)return;", "const sc=document.getElementById('content');if(!sc)return;")

open(path, 'w', encoding='utf-8').write(text)
print("ALL CHANGES APPLIED")
