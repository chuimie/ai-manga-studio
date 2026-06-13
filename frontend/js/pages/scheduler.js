async function renderScheduler() {
  const [configRes, nextRes, logsRes] = await Promise.all([
    fetch("/api/schedule/config").then(r=>r.json()),
    fetch("/api/schedule/next-runs").then(r=>r.json()),
    fetch("/api/schedule/logs?limit=20").then(r=>r.json())
  ]);

  const config   = configRes;
  const nextRuns = nextRes.jobs || [];
  const logs     = logsRes.logs || [];
  const enabled  = config.enabled;

  document.getElementById("mainContent").innerHTML = `
    <div class="grid-2">

      <!-- 左：调度配置 -->
      <div>
        <!-- 全局开关 -->
        <div class="card mb-16">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
              <div class="bold">自动调度</div>
              <div class="text-dim" style="font-size:12px;margin-top:4px">
                开启后按配置时间自动触发生产
              </div>
            </div>
            <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
              <div style="font-size:13px;color:${enabled?"var(--success)":"var(--text-dim)"}">
                ${enabled ? "运行中" : "已停止"}
              </div>
              <div style="position:relative;width:48px;height:26px"
                   onclick="toggleScheduler(${!enabled})">
                <div style="
                  position:absolute;inset:0;border-radius:13px;
                  background:${enabled?"var(--success)":"var(--border-light)"};
                  transition:background 0.2s;cursor:pointer
                "></div>
                <div style="
                  position:absolute;top:3px;
                  left:${enabled?"24px":"3px"};
                  width:20px;height:20px;border-radius:50%;
                  background:white;transition:left 0.2s
                "></div>
              </div>
            </label>
          </div>
        </div>

        <!-- IP任务配置 -->
        <div class="card mb-16">
          <div class="section-header mb-16">
            <div class="bold">📅 每日任务配置</div>
            <button class="btn btn-primary" style="font-size:12px"
              onclick="addScheduleTask()">+ 添加</button>
          </div>

          <div id="scheduleTaskList">
            ${config.daily_tasks?.length
              ? config.daily_tasks.map((task, i) => renderScheduleTask(task, i)).join("")
              : `<div class="text-dim" style="text-align:center;padding:20px;font-size:13px">
                   暂无配置，点击「添加」创建第一个定时任务
                 </div>`
            }
          </div>

          <div style="margin-top:14px">
            <button class="btn btn-primary" style="width:100%"
              onclick="saveScheduleConfig()">
              💾 保存配置
            </button>
          </div>
        </div>

        <!-- 下次执行时间 -->
        <div class="card">
          <div class="bold" style="margin-bottom:12px">⏰ 下次执行计划</div>
          ${nextRuns.length
            ? nextRuns.map(job => `
                <div style="display:flex;justify-content:space-between;
                            padding:8px 0;border-bottom:1px solid var(--border);
                            font-size:13px">
                  <span class="text-sub">每天 ${job.at_time?.slice(0,5)||"—"}</span>
                  <span style="color:var(--primary)">
                    ${job.next_run ? new Date(job.next_run).toLocaleString("zh") : "—"}
                  </span>
                </div>`
              ).join("")
            : `<div class="text-dim" style="font-size:13px">暂无计划任务</div>`
          }
        </div>
      </div>

      <!-- 右：执行日志 -->
      <div>
        <div class="card">
          <div style="display:flex;justify-content:space-between;
                      align-items:center;margin-bottom:14px">
            <div class="bold">📋 调度日志</div>
            <button class="btn btn-ghost" style="font-size:12px"
              onclick="renderScheduler()">刷新</button>
          </div>

          <div style="display:flex;flex-direction:column;gap:8px" id="schedLogs">
            ${logs.length
              ? logs.map(log => renderSchedLog(log)).join("")
              : `<div class="text-dim" style="text-align:center;padding:30px;font-size:13px">
                   暂无日志
                 </div>`
            }
          </div>
        </div>
      </div>
    </div>
  `;
}

// 全局调度任务草稿
let scheduleDraft = null;

function renderScheduleTask(task, index) {
  const ipName = State.ips.find(ip=>ip.ip_id===task.ip_id)?.name || task.ip_id;
  const themes = (task.theme_pool||[]).join("\n");
  return `
    <div style="background:var(--bg-hover);border-radius:8px;padding:14px;
                margin-bottom:10px;border:1px solid var(--border)"
         id="schedTask_${index}">
      <div style="display:flex;justify-content:space-between;
                  align-items:center;margin-bottom:12px">
        <div style="display:flex;align-items:center;gap:8px">
          <div style="
            width:8px;height:8px;border-radius:50%;
            background:${task.enabled?"var(--success)":"var(--text-dim)"}
          "></div>
          <div class="bold">${ipName}</div>
          <div class="text-dim" style="font-size:11px">${task.ip_id}</div>
        </div>
        <button class="btn btn-danger" style="font-size:11px;padding:4px 8px"
          onclick="removeScheduleTask(${index})">删除</button>
      </div>

      <div class="grid-2" style="gap:10px;margin-bottom:10px">
        <div>
          <div class="form-label">生产时间</div>
          <input class="form-input" type="time"
            value="${task.time||"09:00"}"
            onchange="updateTaskField(${index},'time',this.value)">
        </div>
        <div>
          <div class="form-label">每日集数</div>
          <input class="form-input" type="number"
            value="${task.count||2}" min="1" max="10"
            onchange="updateTaskField(${index},'count',parseInt(this.value))">
        </div>
      </div>

      <div style="margin-bottom:10px">
        <div class="form-label">主题池（每行一个，留空则自动生成）</div>
        <textarea class="form-input" rows="3"
          style="resize:vertical"
          placeholder="团子挑战做早饭&#10;团子参加运动会&#10;团子第一次打工"
          onchange="updateTaskField(${index},'theme_pool',
            this.value.split('\\n').filter(t=>t.trim()))"
        >${themes}</textarea>
      </div>

      <div style="display:flex;justify-content:space-between;align-items:center">
        <label style="display:flex;align-items:center;gap:8px;
                      cursor:pointer;font-size:13px">
          <input type="checkbox" ${task.enabled?"checked":""}
            onchange="updateTaskField(${index},'enabled',this.checked)">
          <span class="text-sub">启用此任务</span>
        </label>
        <button class="btn btn-ghost" style="font-size:12px"
          onclick="triggerTaskNow('${task.ip_id}')">
          ▶ 立即执行
        </button>
      </div>
    </div>
  `;
}

function renderSchedLog(log) {
  const TYPE_MAP = {
    scheduler_started: { icon:"🚀", color:"var(--success)", label:"调度器启动" },
    scheduler_stopped: { icon:"⏹",  color:"var(--text-dim)",label:"调度器停止" },
    task_start:        { icon:"▶",  color:"var(--primary)", label:"任务开始"   },
    task_done:         { icon:"✅", color:"var(--success)", label:"任务完成"   },
    episode_done:      { icon:"🎬", color:"var(--success)", label:"集完成"     },
    episode_error:     { icon:"❌", color:"var(--error)",   label:"集失败"     },
    manual_trigger:    { icon:"⚡", color:"var(--warning)", label:"手动触发"   }
  };

  const t = TYPE_MAP[log.event_type] || { icon:"ℹ️", color:"var(--text-dim)", label:log.event_type };
  const detail = log.detail ? JSON.stringify(log.detail) : "";

  return `
    <div style="display:flex;gap:10px;align-items:flex-start;
                padding:8px 0;border-bottom:1px solid var(--border)">
      <div style="font-size:16px;flex-shrink:0">${t.icon}</div>
      <div style="flex:1">
        <div style="display:flex;gap:8px;align-items:center">
          <span style="color:${t.color};font-size:13px">${t.label}</span>
          ${log.ip_id ? `<span class="text-dim" style="font-size:11px">${log.ip_id}</span>` : ""}
        </div>
        ${detail ? `<div class="text-dim" style="font-size:11px;margin-top:2px;
          font-family:monospace">${escHtml(detail)}</div>` : ""}
        <div class="text-dim" style="font-size:10px;margin-top:2px">
          ${log.timestamp?.slice(0,19)||""}
        </div>
      </div>
    </div>
  `;
}

// 调度任务编辑操作
let scheduleTasksLocal = [];

function addScheduleTask() {
  // 加载当前配置
  fetch("/api/schedule/config").then(r=>r.json()).then(config => {
    const ipId = State.ips[0]?.ip_id;
    if (!ipId) { showToast("请先创建IP角色", "error"); return; }
    config.daily_tasks = config.daily_tasks || [];
    config.daily_tasks.push({
      ip_id: ipId, count: 2, time: "09:00",
      enabled: true, theme_pool: []
    });
    saveScheduleConfigDirect(config);
  });
}

function removeScheduleTask(index) {
  fetch("/api/schedule/config").then(r=>r.json()).then(config => {
    config.daily_tasks.splice(index, 1);
    saveScheduleConfigDirect(config);
  });
}

function updateTaskField(index, field, value) {
  // 临存到DOM，统一在点保存时提交
  const el = document.getElementById(`schedTask_${index}`);
  if (!el) return;
  el.dataset[field] = JSON.stringify(value);
}

async function saveScheduleConfig() {
  const res    = await fetch("/api/schedule/config").then(r=>r.json());
  const config = res;

  // 从DOM读取当前表单值
  const taskEls = document.querySelectorAll("[id^='schedTask_']");
  taskEls.forEach((el, i) => {
    if (!config.daily_tasks[i]) return;
    const timeEl   = el.querySelector("input[type=time]");
    const countEl  = el.querySelector("input[type=number]");
    const themeEl  = el.querySelector("textarea");
    const checkEl  = el.querySelector("input[type=checkbox]");
    const ipSel    = el.querySelector("select");

    if (timeEl)  config.daily_tasks[i].time  = timeEl.value;
    if (countEl) config.daily_tasks[i].count = parseInt(countEl.value);
    if (themeEl) config.daily_tasks[i].theme_pool =
      themeEl.value.split("\n").filter(t => t.trim());
    if (checkEl) config.daily_tasks[i].enabled = checkEl.checked;
    if (ipSel)   config.daily_tasks[i].ip_id   = ipSel.value;
  });

  await saveScheduleConfigDirect(config);
}

async function saveScheduleConfigDirect(config) {
  await fetch("/api/schedule/config", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(config)
  });
  showToast("调度配置已保存", "success");
  await renderScheduler();
}

async function toggleScheduler(enabled) {
  await fetch("/api/schedule/toggle", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({enabled})
  });
  showToast(enabled ? "调度器已启动" : "调度器已停止",
            enabled ? "success" : "info");
  await renderScheduler();
}

async function triggerTaskNow(ipId) {
  if (!confirm(`立即执行 ${ipId} 的生产任务？`)) return;
  const res  = await fetch(`/api/schedule/trigger/${ipId}`, {method:"POST"});
  const data = await res.json();
  if (data.error) {
    showToast(data.error, "error");
  } else {
    showToast(`${ipId} 任务已触发，前往生产中心查看日志`, "success");
  }
}