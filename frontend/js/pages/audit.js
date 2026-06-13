// ═══════════════════════════════════════════════
//  Prompt审计
// ═══════════════════════════════════════════════

async function renderAudit() {
  const tb = document.getElementById("topbarActions");
  tb.innerHTML = `
    <select class="form-select" style="width:140px" id="auditDateSel"
      onchange="loadAuditLogs()">
      <option value="">加载日期...</option>
    </select>
    <select class="form-select" style="width:120px" id="auditEngineSel"
      onchange="loadAuditLogs()">
      <option value="">全部引擎</option>
      <option value="script">📝 剧本</option>
      <option value="image">🖼️ 图像</option>
      <option value="video">🎬 视频</option>
      <option value="tts">🔊 配音</option>
      <option value="qc">🔍 质检</option>
      <option value="creator">✨ 工坊</option>
    </select>
    <select class="form-select" style="width:130px" id="auditIpSel"
      onchange="loadAuditLogs()">
      <option value="">全部IP</option>
      ${State.ips.map(ip=>`<option value="${ip.ip_id}">${ip.name}</option>`).join("")}
    </select>
    <button class="btn btn-ghost" onclick="exportAuditLogs()">
      📥 导出
    </button>
  `;

  document.getElementById("mainContent").innerHTML = `
    <!-- 统计行 -->
    <div class="grid-4 mb-16" id="auditStats">
      <div class="stat-card">
        <div class="stat-label">今日调用次数</div>
        <div class="stat-value" id="statTotalCalls">—</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">剧本引擎</div>
        <div class="stat-value" style="color:var(--primary)" id="statScript">—</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">图像引擎</div>
        <div class="stat-value" style="color:var(--accent)" id="statImage">—</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Prompt总字符</div>
        <div class="stat-value" style="color:var(--warning)" id="statChars">—</div>
      </div>
    </div>

    <!-- 日志表格 -->
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;
                  margin-bottom:14px">
        <div class="bold" id="auditTotal">日志列表</div>
        <div style="display:flex;gap:8px;align-items:center">
          <input class="form-input" id="auditSearch"
            placeholder="搜索 stage / log_id..."
            style="width:220px"
            oninput="filterAuditTable()">
        </div>
      </div>

      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-size:13px"
               id="auditTable">
          <thead>
            <tr style="background:var(--bg-hover)">
              <th style="${thStyle()}">时间</th>
              <th style="${thStyle()}">引擎</th>
              <th style="${thStyle()}">阶段</th>
              <th style="${thStyle()}">IP</th>
              <th style="${thStyle()}">集/帧</th>
              <th style="${thStyle()}">模型</th>
              <th style="${thStyle()}">Prompt长度</th>
              <th style="${thStyle()}">操作</th>
            </tr>
          </thead>
          <tbody id="auditTableBody">
            <tr><td colspan="8" style="text-align:center;padding:40px;
                color:var(--text-dim)">
              <div class="spinner"></div>
            </td></tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div style="display:flex;justify-content:space-between;
                  align-items:center;margin-top:14px"
           id="auditPager">
      </div>
    </div>

    <!-- 详情抽屉 -->
    <div id="auditDrawer" style="
      position:fixed; right:-480px; top:0; bottom:0;
      width:480px; background:var(--bg-panel);
      border-left:1px solid var(--border-light);
      z-index:500; transition:right 0.3s ease;
      display:flex; flex-direction:column;
      box-shadow:-8px 0 32px rgba(0,0,0,0.4)
    ">
      <div style="padding:16px 20px;border-bottom:1px solid var(--border);
                  display:flex;justify-content:space-between;align-items:center">
        <div>
          <div class="bold" id="drawerTitle">Prompt详情</div>
          <div class="text-dim" style="font-size:11px" id="drawerMeta"></div>
        </div>
        <button class="modal-close" onclick="closeDrawer()">✕</button>
      </div>
      <div style="flex:1;overflow-y:auto;padding:16px 20px" id="drawerBody"></div>
      <div style="padding:14px 20px;border-top:1px solid var(--border);
                  display:flex;gap:8px">
        <button class="btn btn-ghost" style="font-size:12px"
          onclick="copyDrawerPrompt()">📋 复制Prompt</button>
        <button class="btn btn-ghost" style="font-size:12px"
          onclick="downloadDrawerLog()">📥 下载JSON</button>
      </div>
    </div>
    <div id="drawerOverlay" style="
      display:none; position:fixed; inset:0;
      background:rgba(0,0,0,0.4); z-index:499
    " onclick="closeDrawer()"></div>
  `;

  // 加载日期列表
  await loadAuditDates();
  await loadAuditStats();
  await loadAuditLogs();
}

// 全局审计状态
const AuditState = {
  currentLog:  null,
  allRows:     [],
  offset:      0,
  limit:       50
};

async function loadAuditDates() {
  try {
    const res   = await fetch("/api/audit/dates");
    const data  = await res.json();
    const sel   = document.getElementById("auditDateSel");
    if (!sel) return;
    const today = new Date().toISOString().slice(0,10);
    sel.innerHTML = data.dates.map(d =>
      `<option value="${d}" ${d===today?"selected":""}>${d}</option>`
    ).join("");
  } catch(e) {}
}

async function loadAuditStats() {
  try {
    const date = document.getElementById("auditDateSel")?.value || "";
    const url  = date ? `/api/audit/stats?date=${date}` : "/api/audit/stats";
    const res  = await fetch(url);
    const s    = await res.json();

    const set  = (id, v) => { const el = document.getElementById(id); if(el) el.textContent = v; };
    set("statTotalCalls", s.total_calls ?? "—");
    set("statScript",     s.by_engine?.script  ?? 0);
    set("statImage",      s.by_engine?.image   ?? 0);
    set("statChars",      s.total_prompt_chars
                          ? (s.total_prompt_chars/1000).toFixed(1)+"K" : "—");
  } catch(e) {}
}

async function loadAuditLogs() {
  const body = document.getElementById("auditTableBody");
  if (!body) return;
  body.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:40px">
    <div class="spinner"></div></td></tr>`;

  const date   = document.getElementById("auditDateSel")?.value   || "";
  const engine = document.getElementById("auditEngineSel")?.value || "";
  const ipId   = document.getElementById("auditIpSel")?.value     || "";

  const params = new URLSearchParams();
  if (date)   params.set("date",   date);
  if (engine) params.set("engine", engine);
  if (ipId)   params.set("ip_id",  ipId);
  params.set("limit",  AuditState.limit);
  params.set("offset", AuditState.offset);

  try {
    const res  = await fetch(`/api/audit/logs?${params}`);
    const data = await res.json();
    AuditState.allRows = data.logs || [];

    const total = data.total || 0;
    const totEl = document.getElementById("auditTotal");
    if (totEl) totEl.textContent = `日志列表（共 ${total} 条）`;

    renderAuditTable(AuditState.allRows);
    renderAuditPager(total);
    await loadAuditStats();
  } catch(e) {
    body.innerHTML = `<tr><td colspan="8" style="text-align:center;
      padding:40px;color:var(--error)">加载失败</td></tr>`;
  }
}

function renderAuditTable(logs) {
  const body = document.getElementById("auditTableBody");
  if (!body) return;

  if (!logs.length) {
    body.innerHTML = `<tr><td colspan="8" style="text-align:center;
      padding:40px;color:var(--text-dim)">暂无日志</td></tr>`;
    return;
  }

  const ENGINE_ICONS = {
    script: "📝", image: "🖼️", video: "🎬",
    tts: "🔊", qc: "🔍", creator: "✨"
  };
  const ENGINE_COLORS = {
    script: "var(--primary)", image: "var(--accent)",
    video: "#fc7c5c", tts: "var(--success)",
    qc: "var(--warning)", creator: "#7cf0fc"
  };

  body.innerHTML = logs.map(log => {
    const icon  = ENGINE_ICONS[log.engine]  || "⚙️";
    const color = ENGINE_COLORS[log.engine] || "var(--text-sub)";
    const time  = log.timestamp
      ? log.timestamp.slice(11,19)
      : "—";
    const epStr = log.episode_num != null
      ? `EP${log.episode_num}` : "—";
    const fmStr = log.frame_id != null
      ? ` / F${String(log.frame_id).zfill ? String(log.frame_id).padStart(3,"0") : log.frame_id}` : "";

    // Prompt预览（截取前60字）
    const pText = typeof log.prompt === "string"
      ? log.prompt
      : JSON.stringify(log.prompt);
    const preview = pText.slice(0,60).replace(/\n/g," ") +
                   (pText.length > 60 ? "…" : "");

    return `
      <tr style="border-bottom:1px solid var(--border);cursor:pointer"
          onclick="openDrawer('${log.log_id}', '${log.timestamp?.slice(0,10)||""}')"
          onmouseenter="this.style.background='var(--bg-hover)'"
          onmouseleave="this.style.background=''">
        <td style="${tdStyle()};color:var(--text-dim);font-family:monospace">
          ${time}
        </td>
        <td style="${tdStyle()}">
          <span style="color:${color}">${icon} ${log.engine}</span>
        </td>
        <td style="${tdStyle()};font-family:monospace;font-size:11px;
                   color:var(--text-sub)">
          ${log.stage}
        </td>
        <td style="${tdStyle()};color:var(--text-sub)">
          ${log.ip_id || "—"}
        </td>
        <td style="${tdStyle()};font-family:monospace;font-size:11px">
          ${epStr}${fmStr}
        </td>
        <td style="${tdStyle()};font-size:11px;color:var(--text-dim)">
          ${(log.model || "").replace("agnes-","").replace("mimo-","mimo-")}
        </td>
        <td style="${tdStyle()}">
          <span style="color:var(--text-sub)">${log.prompt_length || 0}</span>
          <span class="text-dim" style="font-size:11px"> 字</span>
        </td>
        <td style="${tdStyle()}">
          <button class="btn btn-ghost" style="font-size:11px;padding:3px 8px"
            onclick="event.stopPropagation();openDrawer('${log.log_id}','${log.timestamp?.slice(0,10)||""}')">
            查看
          </button>
        </td>
      </tr>
      <tr style="border-bottom:1px solid var(--border)">
        <td colspan="8" style="padding:0 12px 8px;font-size:11px;
            color:var(--text-dim);font-family:monospace">
          ${escHtml(preview)}
        </td>
      </tr>
    `;
  }).join("");
}

function renderAuditPager(total) {
  const pager  = document.getElementById("auditPager");
  if (!pager) return;
  const pages  = Math.ceil(total / AuditState.limit);
  const cur    = Math.floor(AuditState.offset / AuditState.limit) + 1;

  pager.innerHTML = `
    <div class="text-dim" style="font-size:12px">
      第 ${AuditState.offset+1}–${Math.min(AuditState.offset+AuditState.limit,total)} 条
      / 共 ${total} 条
    </div>
    <div style="display:flex;gap:6px">
      <button class="btn btn-ghost" style="font-size:12px;padding:5px 10px"
        ${cur<=1?"disabled":""}
        onclick="AuditState.offset=Math.max(0,AuditState.offset-AuditState.limit);loadAuditLogs()">
        ← 上一页
      </button>
      <span style="padding:5px 10px;font-size:12px;color:var(--text-sub)">
        ${cur} / ${pages}
      </span>
      <button class="btn btn-ghost" style="font-size:12px;padding:5px 10px"
        ${cur>=pages?"disabled":""}
        onclick="AuditState.offset+=AuditState.limit;loadAuditLogs()">
        下一页 →
      </button>
    </div>
  `;
}

function filterAuditTable() {
  const kw = document.getElementById("auditSearch")?.value.toLowerCase() || "";
  if (!kw) {
    renderAuditTable(AuditState.allRows);
    return;
  }
  const filtered = AuditState.allRows.filter(log =>
    (log.stage  || "").toLowerCase().includes(kw) ||
    (log.log_id || "").toLowerCase().includes(kw) ||
    (log.ip_id  || "").toLowerCase().includes(kw)
  );
  renderAuditTable(filtered);
}

async function openDrawer(logId, date) {
  try {
    const url = date
      ? `/api/audit/logs/${logId}?date=${date}`
      : `/api/audit/logs/${logId}`;
    const res  = await fetch(url);
    const log  = await res.json();

    if (log.error) { showToast("日志不存在", "error"); return; }
    AuditState.currentLog = log;

    document.getElementById("drawerTitle").textContent =
      `${log.engine} / ${log.stage}`;
    document.getElementById("drawerMeta").textContent =
      `${log.log_id} · ${log.timestamp?.slice(0,19)||""}`;

    const promptStr = typeof log.prompt === "string"
      ? log.prompt
      : JSON.stringify(log.prompt, null, 2);

    const responseStr = log.response_preview || "（无响应记录）";

    document.getElementById("drawerBody").innerHTML = `
      <!-- 基本信息 -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;
                  margin-bottom:16px">
        ${metaItem("引擎",   log.engine)}
        ${metaItem("阶段",   log.stage)}
        ${metaItem("IP",     log.ip_id || "—")}
        ${metaItem("集数",   log.episode_num != null ? `EP${log.episode_num}` : "—")}
        ${metaItem("帧",     log.frame_id   != null ? `F${log.frame_id}` : "—")}
        ${metaItem("模型",   log.model || "—")}
        ${metaItem("长度",   `${log.prompt_length||0} 字`)}
        ${metaItem("Hash",   `<code style="font-size:10px">${log.prompt_hash||""}</code>`)}
      </div>

      <hr class="divider">

      <!-- Prompt内容 -->
      <div style="margin-bottom:4px;font-size:12px;color:var(--text-sub);
                  font-weight:600;text-transform:uppercase;letter-spacing:.05em">
        Prompt
      </div>
      <div style="background:#0a0a10;border:1px solid var(--border);
                  border-radius:6px;padding:12px;font-family:monospace;
                  font-size:12px;line-height:1.7;color:#c8d8ff;
                  white-space:pre-wrap;word-break:break-all;
                  max-height:320px;overflow-y:auto;margin-bottom:14px"
           id="drawerPromptBox">
${escHtml(promptStr)}
      </div>

      <!-- 响应预览 -->
      <div style="margin-bottom:4px;font-size:12px;color:var(--text-sub);
                  font-weight:600;text-transform:uppercase;letter-spacing:.05em">
        响应预览
      </div>
      <div style="background:#0a0a10;border:1px solid var(--border);
                  border-radius:6px;padding:12px;font-family:monospace;
                  font-size:11px;line-height:1.6;color:#90b090;
                  white-space:pre-wrap;word-break:break-all;
                  max-height:200px;overflow-y:auto;margin-bottom:14px">
${escHtml(responseStr)}
      </div>

      <!-- Extra信息 -->
      ${log.extra && Object.keys(log.extra).length ? `
        <div style="margin-bottom:4px;font-size:12px;color:var(--text-sub);
                    font-weight:600;text-transform:uppercase">附加信息</div>
        <div style="background:#0a0a10;border:1px solid var(--border);
                    border-radius:6px;padding:12px;font-family:monospace;
                    font-size:11px;color:var(--text-dim);
                    white-space:pre-wrap;max-height:160px;overflow-y:auto">
${escHtml(JSON.stringify(log.extra, null, 2))}
        </div>` : ""}
    `;

    // 打开抽屉
    document.getElementById("auditDrawer").style.right   = "0";
    document.getElementById("drawerOverlay").style.display = "block";
  } catch(e) {
    showToast("加载详情失败", "error");
  }
}

function closeDrawer() {
  document.getElementById("auditDrawer").style.right     = "-480px";
  document.getElementById("drawerOverlay").style.display = "none";
}

function copyDrawerPrompt() {
  if (!AuditState.currentLog) return;
  const p = typeof AuditState.currentLog.prompt === "string"
    ? AuditState.currentLog.prompt
    : JSON.stringify(AuditState.currentLog.prompt, null, 2);
  navigator.clipboard.writeText(p)
    .then(() => showToast("Prompt已复制", "success"))
    .catch(() => showToast("复制失败", "error"));
}

function downloadDrawerLog() {
  if (!AuditState.currentLog) return;
  const blob = new Blob(
    [JSON.stringify(AuditState.currentLog, null, 2)],
    {type: "application/json"}
  );
  const a    = document.createElement("a");
  a.href     = URL.createObjectURL(blob);
  a.download = `prompt_${AuditState.currentLog.log_id}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function exportAuditLogs() {
  const date   = document.getElementById("auditDateSel")?.value   || "";
  const engine = document.getElementById("auditEngineSel")?.value || "";
  const params = new URLSearchParams();
  if (date)   params.set("date",   date);
  if (engine) params.set("engine", engine);
  params.set("limit", 9999);

  try {
    const res  = await fetch(`/api/audit/logs?${params}`);
    const data = await res.json();
    const blob = new Blob(
      [JSON.stringify(data.logs, null, 2)],
      {type: "application/json"}
    );
    const a    = document.createElement("a");
    a.href     = URL.createObjectURL(blob);
    a.download = `audit_${date||"all"}_${engine||"all"}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    showToast(`已导出 ${data.logs.length} 条日志`, "success");
  } catch(e) {
    showToast("导出失败", "error");
  }
}