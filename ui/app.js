/* ===== 生死狙击 AI 助手 前端逻辑 =====
   后端通过 pywebview 暴露 window.pywebview.api（见 app.py）。
   日志采用【前端轮询】模式：每 0.4s 调 api().get_new_logs(cursor) 拉增量。
   （不要改回后端主动 evaluate_js 推送——那个调用每行日志都会激活一次
     助手窗口，导致游戏刚点开的界面立刻失焦弹「点击游戏画面继续操作」。） */

const SniperUI = {
  // 后端调用：追加一行日志（line 为字符串）
  appendLog(line) {
    const term = document.getElementById('terminal');
    if (!term) return;
    const div = document.createElement('div');
    div.className = 'term-line ' + SniperUI._cls(line);
    div.textContent = line;
    term.appendChild(div);
    const cap = 2000;
    while (term.childElementCount > cap) term.removeChild(term.firstChild);
    // 自动滚动：仅在勾选且当前已在底部附近时才下滚；用户往上翻阅时不打扰
    const chk = document.getElementById('chkAutoscroll');
    const nearBottom = term.scrollHeight - term.scrollTop - term.clientHeight < 60;
    if (nearBottom && (!chk || chk.checked)) term.scrollTop = term.scrollHeight;
  },
  _cls(line) {
    if (/错误|error|exception|traceback/i.test(line)) return 'err';
    if (/已启动|开始|成功|ok|created/i.test(line)) return 'ok';
    if (/模型|置信|目标|点击|decision|决策/i.test(line)) return 'info';
    return 'bot';
  },
  // 后端调用：更新运行状态
  setRunning(running) {
    const pill = document.getElementById('statusPill');
    const txt = document.getElementById('statusText');
    pill.classList.toggle('running', running);
    pill.classList.toggle('stopped', !running);
    txt.textContent = running ? '运行中' : '已停止';
    const ds = document.getElementById('dashStatus');
    if (ds) ds.textContent = running ? '运行中' : '未启动';
  },
  // 后端调用：刷新静态信息（模型/自动/窗口）
  setInfo(info) {
    const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
    set('dashModel', info.model || '—');
    set('dashAuto', info.auto ? '开' : '关');
    set('dashWindow', info.window || '—');
  },
  // 后端调用：更新帧数
  setFrames(n) {
    const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
    set('dashFrames', n);
  },
  // 前端：更新当前脚本名
  setScript(name) {
    const e = document.getElementById('dashScript');
    if (e) e.textContent = name || '—';
  }
};
window.SniperUI = SniperUI;

/* ---------- 导航切换 ---------- */
function switchView(view) {
  document.querySelectorAll('.navbtn[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + view));
}
document.querySelectorAll('.navbtn[data-view]').forEach(b => {
  b.addEventListener('click', () => switchView(b.dataset.view));
});

/* ---------- 调后端 ---------- */
const api = () => window.pywebview.api;

// 当前选中的脚本（从脚本列表「设为当前」得到），运行时优先用它的配置
let currentScript = null;

async function startBot() {
  const opts = buildStartOpts();
  try { await api().start(opts); SniperUI.setRunning(true); } catch (e) { alert('启动失败: ' + e); }
}
async function stopBot() {
  try { await api().stop(); SniperUI.setRunning(false); } catch (e) { alert('停止失败: ' + e); }
}
async function restartBot() {
  const opts = buildStartOpts();
  try { await api().restart(opts); SniperUI.setRunning(true); } catch (e) { alert('重启失败: ' + e); }
}

// 从设置表单收集当前值（不强制覆盖，交给后端按非空处理）
function collectForm() {
  const f = document.getElementById('settingsForm');
  const g = n => f.elements[n] ? f.elements[n].value : '';
  const gc = n => f.elements[n] ? f.elements[n].checked : false;
  return {
    model_url: g('model_url'),
    model: g('model'),
    window_title: g('window_title'),
    confidence: g('confidence'),
    loop_interval: g('loop_interval'),
    auto_execute: gc('auto_execute'),
    hold_fire: gc('hold_fire'),
    openai_compat: gc('openai_compat'),
  };
}

// 运行时配置：若选了当前脚本，则用脚本配置覆盖表单对应项（脚本更具体），并带上 prompt
function buildStartOpts() {
  const opts = collectForm();
  if (currentScript) {
    const s = currentScript;
    if (s.auto_execute !== undefined) opts.auto_execute = s.auto_execute;
    if (s.prompt) opts.prompt = s.prompt;
    if (s.program) opts.program = s.program;   // 绑定要运行的程序（如 auto_lobby.py）
    if (s.dry) opts.dry = true;                 // 仅识别不点击
    SniperUI.setScript(s.name || '(未命名脚本)');
  } else {
    SniperUI.setScript('—');
  }
  return opts;
}

/* ---------- 按钮 ---------- */
document.getElementById('btnStart').addEventListener('click', startBot);
document.getElementById('btnStop').addEventListener('click', stopBot);
document.getElementById('btnRestart').addEventListener('click', restartBot);
document.getElementById('btnQuit').addEventListener('click', () => { try { api().quit(); } catch (e) {} });
document.getElementById('btnClearLog').addEventListener('click', () => { document.getElementById('terminal').innerHTML = ''; });

/* ---------- 窗口置顶 ---------- */
let onTop = false;
document.getElementById('btnOnTop').addEventListener('click', async () => {
  try {
    const r = await api().set_on_top(!onTop);
    if (r && r.ok) {
      onTop = !onTop;
      document.getElementById('btnOnTop').classList.toggle('btn-on', onTop);
    } else {
      alert('置顶失败: ' + (r && r.msg || '未知错误'));
    }
  } catch (e) { alert('置顶失败: ' + e); }
});

/* ---------- 设置表单 ---------- */
document.getElementById('settingsForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = collectForm();
  const msg = document.getElementById('settingsMsg');
  try {
    const r = await api().save_config(data);
    msg.textContent = r && r.ok ? '已保存（重启后生效）' : '保存失败';
    msg.className = 'msg ' + (r && r.ok ? 'ok' : 'err');
  } catch (err) { msg.textContent = '保存失败: ' + err; msg.className = 'msg err'; }
});

/* ---------- 环境自检 ---------- */
document.getElementById('btnCheckEnv').addEventListener('click', async () => {
  const items = document.querySelectorAll('#envList .env-item');
  items.forEach(it => { it.className = 'env-item pending'; it.querySelector('.state').textContent = '检测中…'; });
  try {
    const res = await api().check_env();
    const map = { python: 0, main_py: 1, ollama: 2, model: 3 };
    for (const k in res) {
      const idx = map[k]; if (idx === undefined) continue;
      const it = items[idx];
      it.className = 'env-item ' + (res[k] ? 'ok' : 'err');
      it.querySelector('.state').textContent = res[k] ? '正常' : '异常';
    }
  } catch (e) {
    items.forEach(it => { it.className = 'env-item err'; it.querySelector('.state').textContent = '检测失败'; });
  }
});

/* ---------- 脚本列表 ---------- */
let scriptList = [];
let editingScriptId = null; // null = 新增

function renderScripts() {
  const box = document.getElementById('scriptList');
  if (!box) return;
  box.innerHTML = '';
  if (!scriptList.length) {
    box.innerHTML = '<div class="script-hint">还没有脚本。点右上角「＋ 新增脚本」创建一个。</div>';
    return;
  }
  for (const s of scriptList) {
    const card = document.createElement('div');
    card.className = 'script-card' + (s.id === currentScript?.id ? ' active' : '') + (s.enabled === false ? ' disabled' : '');
    const activeTag = s.id === currentScript?.id ? '<span class="sc-current-tag">当前</span>' : '';
    const progLine = (s.program ? esc(s.program) : 'main.py') + (s.dry ? '（仅识别）' : '');
    card.innerHTML =
      '<div class="sc-head"><span class="sc-name">' + esc(s.name || '(未命名)') + '</span></div>' +
      '<div class="sc-desc">' + esc(s.desc || '') + '</div>' +
      '<div class="sc-prog">程序：' + progLine + '</div>' +
      (s.prompt ? '<div class="sc-prompt">' + esc(s.prompt) + '</div>' : '') +
      '<div class="sc-actions">' +
        '<button class="btn btn-sm btn-primary" data-act="current" data-id="' + s.id + '">设为当前</button>' +
        '<button class="btn btn-sm" data-act="edit" data-id="' + s.id + '">编辑</button>' +
        '<button class="btn btn-sm" data-act="del" data-id="' + s.id + '">删除</button>' +
        '<label class="chk"><input type="checkbox" data-act="enable" data-id="' + s.id + '"' + (s.enabled !== false ? ' checked' : '') + '/> 启用</label>' +
        activeTag +
      '</div>';
    box.appendChild(card);
  }
  box.querySelectorAll('[data-act]').forEach(b => {
    b.addEventListener('click', () => onScriptAction(b.dataset.act, b.dataset.id));
  });
}

function esc(t) {
  return String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

async function onScriptAction(act, id) {
  if (act === 'current') {
    const s = scriptList.find(x => x.id === id);
    if (!s) return;
    try { await api().set_active_script(id); } catch (e) {}
    currentScript = s;
    SniperUI.setScript(s.name || '(未命名)');
    renderScripts();
  } else if (act === 'edit') {
    openScriptModal(id);
  } else if (act === 'del') {
    if (!confirm('确定删除脚本「' + (scriptList.find(x => x.id === id)?.name || '') + '」？')) return;
    scriptList = scriptList.filter(x => x.id !== id);
    if (currentScript && currentScript.id === id) { currentScript = null; SniperUI.setScript('—'); }
    try { await api().save_scripts(scriptList); } catch (e) { alert('保存失败: ' + e); }
    renderScripts();
  } else if (act === 'enable') {
    const s = scriptList.find(x => x.id === id);
    if (s) { s.enabled = event.target.checked; try { await api().save_scripts(scriptList); } catch (e) {} renderScripts(); }
  }
}

function openScriptModal(id) {
  editingScriptId = id || null;
  const s = id ? scriptList.find(x => x.id === id) : {};
  document.getElementById('scriptModalTitle').textContent = id ? '编辑脚本' : '新增脚本';
  document.getElementById('scName').value = s.name || '';
  document.getElementById('scDesc').value = s.desc || '';
  document.getElementById('scPrompt').value = s.prompt || '';
  document.getElementById('scAuto').checked = s.auto_execute !== false;
  document.getElementById('scriptModalMask').classList.add('show');
}

function closeScriptModal() {
  document.getElementById('scriptModalMask').classList.remove('show');
  editingScriptId = null;
}

async function saveScriptModal() {
  const data = {
    name: document.getElementById('scName').value.trim(),
    desc: document.getElementById('scDesc').value.trim(),
    prompt: document.getElementById('scPrompt').value.trim(),
    auto_execute: document.getElementById('scAuto').checked,
    enabled: true,
  };
  if (!data.name) { alert('请填写脚本名称'); return; }
  if (editingScriptId) {
    const s = scriptList.find(x => x.id === editingScriptId);
    if (s) Object.assign(s, data);
  } else {
    data.id = 'sc_' + Date.now().toString(36);
    scriptList.push(data);
  }
  try {
    await api().save_scripts(scriptList);
    closeScriptModal();
    renderScripts();
  } catch (e) { alert('保存失败: ' + e); }
}

async function loadScripts() {
  try {
    const res = await api().get_scripts();
    scriptList = res.scripts || [];
    currentScript = res.active ? scriptList.find(x => x.id === res.active) || null : null;
    SniperUI.setScript(currentScript ? (currentScript.name || '(未命名)') : '—');
    renderScripts();
  } catch (e) { console.error('loadScripts failed', e); }
}

document.getElementById('btnNewScript').addEventListener('click', () => openScriptModal(null));
document.getElementById('scCancel').addEventListener('click', closeScriptModal);
document.getElementById('scSave').addEventListener('click', saveScriptModal);
document.getElementById('scriptModalMask').addEventListener('click', (e) => {
  if (e.target.id === 'scriptModalMask') closeScriptModal();
});

/* ---------- 初始化 ---------- */
function applyConfig(cfg) {
  if (!cfg) return;
  const f = document.getElementById('settingsForm');
  const set = (n, v) => { if (f.elements[n]) f.elements[n].value = v; };
  const setc = (n, v) => { if (f.elements[n]) f.elements[n].checked = !!v; };
  set('model_url', cfg.model_url);
  set('model', cfg.model);
  set('window_title', cfg.window_title);
  set('confidence', cfg.confidence);
  set('loop_interval', cfg.loop_interval);
  setc('auto_execute', cfg.auto_execute);
  setc('hold_fire', cfg.hold_fire);
  setc('openai_compat', cfg.openai_compat);
  SniperUI.setInfo({ model: cfg.model, auto: cfg.auto_execute, window: cfg.window_title });
}

window.pywebview ? boot() : window.addEventListener('pywebviewready', boot);

let logCursor = 0;   // 已拉取的日志游标（后端 _total 计数）

async function pollLogs() {
  try {
    const r = await api().get_new_logs(logCursor);
    if (r && r.lines && r.lines.length) {
      r.lines.forEach(l => SniperUI.appendLog(l));
      logCursor = r.next;
    }
  } catch (e) { /* 后端重启等瞬态错误，下轮再拉 */ }
}

async function boot() {
  try {
    const cfg = await api().get_config();
    applyConfig(cfg);
    const running = await api().status();
    SniperUI.setRunning(running);
    await loadScripts();
    await pollLogs();          // 先拉一次存量日志
    setInterval(pollLogs, 400); // 之后每 0.4s 拉增量
  } catch (e) { console.error(e); }
}
