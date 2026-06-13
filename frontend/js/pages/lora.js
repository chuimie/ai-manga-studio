async function renderLora() {
  // 加载所有LoRA状态
  const res    = await fetch("/api/lora/status").then(r=>r.json());
  const ips    = State.ips;

  document.getElementById("mainContent").innerHTML = `
    <!-- 说明栏 -->
    <div class="card mb-16" style="border-color:var(--primary);
         background:rgba(124,92,252,0.05)">
      <div style="display:flex;gap:14px;align-items:flex-start">
        <div style="font-size:28px">🧬</div>
        <div>
          <div class="bold" style="margin-bottom:6px">LoRA训练说明</div>
          <div class="text-sub" style="font-size:13px;line-height:1.8">
            每个IP需训练专属LoRA权重，确保跨集角色视觉一致性≥95%。<br>
            流程：生成30张参考图 → 构建训练集 → 提交云端GPU训练（RunPod）→
            自动下载权重。<br>
            <span style="color:var(--warning)">
              预计耗时：2~4小时 | 单IP成本：约$1~3
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- IP卡片列表 -->
    <div class="grid-3" id="loraGrid">
      ${ips.length
        ? ips.map(ip => renderLoraCard(ip, res[ip.ip_id])).join("")
        : `<div class="empty-state" style="grid-column:1/-1">
             <div class="empty-icon">🎭</div>
             <div>请先创建IP角色</div>
           </div>`
      }
    </div>
  `;

  // 启动轮询（训练中的IP）
  startLoraPolling();
}

function renderLoraCard(ip, loraStatus) {
  const status   = loraStatus?.status || "not_started";
  const progress = loraStatus?.progress || 0;
  const hasLora  = status === "completed";

  const STATUS_MAP = {
    not_started:     { label:"未训练",   color:"var(--text-dim)",  icon:"⚪" },
    queued:          { label:"排队中",   color:"var(--text-sub)",  icon:"🕐" },
    generating_refs: { label:"生成参考图",color:"var(--primary)",  icon:"📸" },
    building_dataset:{ label:"构建数据集",color:"var(--primary)",  icon:"📁" },
    training:        { label:"训练中",   color:"var(--warning)",   icon:"⚡" },
    downloading:     { label:"下载权重", color:"var(--primary)",   icon:"⬇️" },
    completed:       { label:"已完成",   color:"var(--success)",   icon:"✅" },
    failed:          { label:"训练失败", color:"var(--error)",     icon:"❌" },
    deleted:         { label:"已删除",   color:"var(--text-dim)",  icon:"🗑️" }
  };

  const s      = STATUS_MAP[status] || STATUS_MAP.not_started;
  const isRun  = ["queued","generating_refs","building_dataset",
                  "training","downloading"].includes(status);

  return `
    <div class="card" id="loraCard_${ip.ip_id}">
      <div style="display:flex;justify-content:space-between;
                  align-items:flex-start;margin-bottom:14px">
        <div>
          <div class="bold" style="margin-bottom:4px">${ip.name}</div>
          <div class="text-dim" style="font-size:11px">${ip.ip_id}</div>
        </div>
        <div style="color:${s.color};font-size:13px;font-weight:500">
          ${s.icon} ${s.label}
        </div>
      </div>

      <!-- 进度条（训练中显示）-->
      ${isRun ? `
        <div style="margin-bottom:14px">
          <div class="progress-track">
            <div class="progress-fill" style="width:${progress}%"></div>
          </div>
          <div class="text-dim" style="font-size:11px;margin-top:4px">
            ${progress}%
          </div>
        </div>` : ""}

      <!-- 权重信息 -->
      ${hasLora ? `
        <div style="background:var(--bg-hover);border-radius:6px;
                    padding:10px;margin-bottom:14px;font-size:12px">
          <div class="text-dim" style="margin-bottom:4px">权重文件</div>
          <div style="font-family:monospace;color:var(--success)">
            models/lora/${ip.ip_id}.safetensors
          </div>
          ${loraStatus?.updated_at ? `
            <div class="text-dim" style="margin-top:4px">
              训练完成：${formatDate(loraStatus.updated_at)}
            </div>` : ""}
        </div>` : ""}

      <!-- 错误信息 -->
      ${status==="failed" && loraStatus?.error ? `
        <div style="background:rgba(252,92,92,0.1);border:1px solid var(--error);
                    border-radius:6px;padding:8px;margin-bottom:14px;
                    font-size:11px;color:var(--error)">
          ${loraStatus.error}
        </div>` : ""}

      <!-- 操作按钮 -->
      <div style="display:flex;gap:6px">
        ${!isRun ? `
          <button class="btn btn-primary" style="flex:1;font-size:12px"
            onclick="startLoraTraining('${ip.ip_id}')"
            ${hasLora?"":""}
          >
            ${hasLora ? "🔄 重新训练" : "🚀 开始训练"}
          </button>` : `
          <button class="btn btn-ghost" style="flex:1;font-size:12px" disabled>
            <span class="spinner" style="width:14px;height:14px"></span>
            训练中...
          </button>`
        }
        ${hasLora ? `
          <button class="btn btn-ghost" style="font-size:12px;padding:7px 10px"
            onclick="testLoraConsistency('${ip.ip_id}')">
            🔍 测试一致性
          </button>
          <button class="btn btn-danger" style="font-size:12px;padding:7px 10px"
            onclick="deleteLoraWeight('${ip.ip_id}')">
            🗑️
          </button>` : ""}
      </div>
    </div>
  `;
}

async function startLoraTraining(ipId) {
  if (!confirm(`确认为 ${ipId} 启动LoRA训练？\n预计耗时2~4小时，成本约$1~3。`)) return;
  try {
    const res  = await fetch("/api/lora/train", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ip_id: ipId})
    });
    const data = await res.json();
    showToast(data.message || "训练任务已提交", "success");
    await renderLora();
  } catch(e) {
    showToast("提交失败：" + e.message, "error");
  }
}

async function deleteLoraWeight(ipId) {
  if (!confirm(`删除 ${ipId} 的LoRA权重？下次生产将无角色一致性保证。`)) return;
  await fetch(`/api/lora/${ipId}`, {method:"DELETE"});
  showToast("权重已删除", "info");
  await renderLora();
}

async function testLoraConsistency(ipId) {
  showToast("生成测试图中...", "info");
  // 触发生成3张测试图，检查一致性
  try {
    const res  = await fetch("/api/generate-preview", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({draft: {
        appearance: State.ips.find(ip=>ip.ip_id===ipId)?.visual?.appearance || "",
        art_style:  State.ips.find(ip=>ip.ip_id===ipId)?.visual?.style || ""
      }})
    });
    const data = await res.json();
    showToast("测试图已生成，请在剧集库查看", "success");
  } catch(e) {
    showToast("测试失败", "error");
  }
}

// 轮询训练中的IP状态
let loraPollingTimer = null;
function startLoraPolling() {
  if (loraPollingTimer) clearInterval(loraPollingTimer);
  loraPollingTimer = setInterval(async () => {
    if (State.currentPage !== "lora") {
      clearInterval(loraPollingTimer);
      return;
    }
    const res = await fetch("/api/lora/status").then(r=>r.json());
    const hasActive = Object.values(res).some(s =>
      ["queued","generating_refs","building_dataset","training","downloading"]
      .includes(s.status)
    );
    if (hasActive) {
      // 更新进度条
      for (const [ipId, status] of Object.entries(res)) {
        const card = document.getElementById(`loraCard_${ipId}`);
        if (card) {
          const ip = State.ips.find(ip => ip.ip_id === ipId);
          if (ip) card.outerHTML = renderLoraCard(ip, status);
        }
      }
    } else {
      clearInterval(loraPollingTimer);
    }
  }, 5000);
}