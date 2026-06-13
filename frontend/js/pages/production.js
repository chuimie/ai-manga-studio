// ═══════════════════════════════════════════════
//  生产中心
// ═══════════════════════════════════════════════
function renderProduction() {
  const ipOptions = State.ips.map(ip =>
    `<option value="${ip.ip_id}" ${State.selectedIp===ip.ip_id?"selected":""}>
       ${ip.name}（${ip.ip_id}）
     </option>`
  ).join("");

  document.getElementById("mainContent").innerHTML = `
    <div class="production-layout">

      <!-- 左：控制面板 -->
      <div>
        <div class="card mb-16">
          <div class="card-title">⚡ 生产配置</div>

          <div class="form-group">
            <label class="form-label">选择IP角色</label>
            ${State.ips.length
              ? `<select class="form-select" id="prodIpSelect">${ipOptions}</select>`
              : `<div style="color:var(--text-dim);font-size:13px;padding:10px 0">
                   暂无IP，请先
                   <span style="color:var(--primary);cursor:pointer"
                         onclick="navigate('creator')">创建角色</span>
                 </div>`
            }
          </div>

          <div class="form-group">
            <label class="form-label">本集主题（可选）</label>
            <input class="form-input" id="prodTheme"
              placeholder="留空则自动生成，如：团子挑战做早饭">
          </div>

          <div class="form-group">
            <label class="form-label">生产集数</label>
            <div class="count-input">
              <button class="count-btn" onclick="adjustCount(-1)">−</button>
              <div class="count-display" id="countDisplay">1</div>
              <button class="count-btn" onclick="adjustCount(1)">+</button>
              <span class="text-dim" style="font-size:12px">
                预估成本：$<span id="estCost">0.77</span>
              </span>
            </div>
          </div>

          <button class="btn btn-primary" style="width:100%;padding:12px"
            onclick="startProduction()" id="startBtn">
            ⚡ 开始生产
          </button>
        </div>

        <!-- 成本预览 -->
        <div class="card">
          <div class="card-title">💰 成本明细</div>
          <table class="cost-table">
            <tr><td>剧本引擎</td>
                <td style="text-align:right;color:var(--text-sub)">~$0.08/集</td></tr>
            <tr><td>视觉引擎</td>
                <td style="text-align:right;color:var(--text-sub)">~$0.15/集</td></tr>
            <tr><td>视频引擎</td>
                <td style="text-align:right;color:var(--text-sub)">~$1.20/集</td></tr>
            <tr><td>配音引擎</td>
                <td style="text-align:right;color:var(--text-sub)">~$0.10/集</td></tr>
            <tr style="font-weight:600">
              <td>合计</td>
              <td style="text-align:right;color:var(--warning)">~$1.53/集</td></tr>
          </table>
        </div>
      </div>

      <!-- 右：日志 + 队列 -->
      <div>
        <div class="section-header mb-16">
          <div class="section-title">📋 实时生产日志</div>
          <button class="btn btn-ghost" style="font-size:12px"
            onclick="clearLogs()">清空</button>
        </div>

        <div class="log-panel" id="logPanel">
          <div class="log-line log-info">
            <span class="log-time">${now()}</span>
            等待生产任务...
          </div>
        </div>

        <div style="margin-top:20px">
          <div class="section-title mb-16">🔄 任务队列</div>
          <div id="queueList">
            <div class="text-dim" style="font-size:13px;text-align:center;padding:20px">
              暂无任务
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  initProductionWs();
  updateEstCost();
}

function adjustCount(delta) {
  State.productionCount = Math.max(1, Math.min(10, State.productionCount + delta));
  document.getElementById("countDisplay").textContent = State.productionCount;
  updateEstCost();
}

function updateEstCost() {
  const cost = (State.productionCount * 1.53).toFixed(2);
  const el   = document.getElementById("estCost");
  if (el) el.textContent = cost;
}

async function startProduction() {
  const ipId  = document.getElementById("prodIpSelect")?.value;
  const theme = document.getElementById("prodTheme")?.value || null;

  if (!ipId) {
    showToast("请先选择IP角色", "error");
    return;
  }

  const btn = document.getElementById("startBtn");
  btn.disabled    = true;
  btn.textContent = "⏳ 提交中...";

  try {
    const res = await fetch("/api/production/start", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        ip_id: ipId, count: State.productionCount, theme
      })
    });
    const data = await res.json();
    showToast(`✅ 生产任务已启动：${data.count}集`, "success");
    appendLog(`🚀 任务启动：${ipId} × ${State.productionCount}集`, "success");
    refreshQueue();
  } catch(e) {
    showToast("启动失败：" + e.message, "error");
  } finally {
    btn.disabled    = false;
    btn.textContent = "⚡ 开始生产";
  }
}

function initProductionWs() {
  const clientId = "browser_" + Date.now();
  if (State.productionWs) State.productionWs.close();
  State.productionWs = new WebSocket(`ws://${location.host}/ws/production/${clientId}`);
  State.productionWs.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "log") {
      appendLog(data.message, data.level);
      if (data.level === "success" && data.message.includes("完成")) {
        refreshQueue();
      }
    }
  };
}

function appendLog(msg, level="info") {
  const panel = document.getElementById("logPanel");
  if (!panel) return;
  const div   = document.createElement("div");
  div.className = `log-line log-${level}`;
  div.innerHTML = `<span class="log-time">${now()}</span>${escHtml(msg)}`;
  panel.appendChild(div);
  panel.scrollTop = panel.scrollHeight;
}

function clearLogs() {
  const p = document.getElementById("logPanel");
  if (p) p.innerHTML = "";
}

async function refreshQueue() {
  try {
    const res  = await fetch("/api/production/status");
    const data = await res.json();
    const list = document.getElementById("queueList");
    if (!list) return;

    if (!data.queue?.length) {
      list.innerHTML = `<div class="text-dim" style="font-size:13px;text-align:center;padding:20px">
        暂无任务</div>`;
      return;
    }
    list.innerHTML = data.queue.map(t => `
      <div class="queue-item">
        <div class="queue-status ${statusClass(t.status)}"></div>
        <div style="flex:1">
          <div style="font-size:13px;font-weight:500">${t.ip_id}</div>
          <div class="text-dim" style="font-size:11px">${t.count}集 · ${t.task_id}</div>
        </div>
        <div style="font-size:12px;color:var(--text-sub)">${t.status}</div>
      </div>
    `).join("");
  } catch(e) {}
}

function statusClass(s) {
  return s==="running" ? "status-running"
       : s==="completed" ? "status-done"
       : s==="error" ? "status-error"
       : "status-waiting";
}