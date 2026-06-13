// ═══════════════════════════════════════════════
//  IP管理
// ═══════════════════════════════════════════════
function renderIpManager() {
  const tb = document.getElementById("topbarActions");
  tb.innerHTML = `
    <button class="btn btn-primary" onclick="navigate('creator')">
      ✨ 创建新IP
    </button>
  `;

  const c = document.getElementById("mainContent");
  if (!State.ips.length) {
    c.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎭</div>
        <div style="font-size:16px;font-weight:600;margin-bottom:8px">还没有IP</div>
        <div class="text-sub" style="margin-bottom:20px">
          去角色卡工坊创建你的第一个IP角色
        </div>
        <button class="btn btn-primary" onclick="navigate('creator')">
          ✨ 创建第一个IP
        </button>
      </div>`;
    return;
  }

  c.innerHTML = `
    <div class="grid-3">
      ${State.ips.map(ip => `
        <div class="ip-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div class="ip-avatar">🎭</div>
            <div style="display:flex;gap:6px">
              <button class="btn btn-ghost" style="padding:4px 8px;font-size:11px"
                onclick="produceNow('${ip.ip_id}')">⚡ 生产</button>
            </div>
          </div>
          <div class="ip-name">${ip.name}</div>
          <div class="ip-meta">${ip.ip_id}</div>
          <div class="ip-tags">
            ${ip.world?.genre  ? `<span class="tag">${ip.world.genre}</span>` : ""}
            ${ip.world?.tone   ? `<span class="tag">${ip.world.tone}</span>`  : ""}
            ${ip.world?.pacing ? `<span class="tag">${ip.world.pacing}</span>`: ""}
          </div>
          <div class="ip-stats">
            <span>🎬 ${ip.episode_count||0} 集</span>
            <span>🎙️ ${ip.voice?.method||"VoiceDesign"}</span>
          </div>
          <hr class="divider" style="margin:10px 0">
          <div style="font-size:12px;color:var(--text-dim)">
            <div>性格：${(ip.character?.核心性格||[]).join(" · ")}</div>
            <div style="margin-top:4px">世界：${ip.world?.setting||""}</div>
          </div>
          <div class="ip-card-actions" style="margin-top:12px">
            <button class="btn btn-ghost" style="flex:1;font-size:12px"
              onclick="viewIpEpisodes('${ip.ip_id}')">查看剧集</button>
            <button class="btn btn-danger" style="font-size:12px;padding:6px 12px"
              onclick="deleteIp('${ip.ip_id}')">删除</button>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

async function deleteIp(ipId) {
  if (!confirm(`确认删除 ${ipId}？此操作不可恢复。`)) return;
  await fetch(`/api/ips/${ipId}`, { method: "DELETE" });
  showToast("IP已删除", "info");
  await navigate("ip-manager");
}

function viewIpEpisodes(ipId) {
  State.selectedIp = ipId;
  navigate("library");
}

async function produceNow(ipId) {
  State.selectedIp = ipId;
  await navigate("production");
}