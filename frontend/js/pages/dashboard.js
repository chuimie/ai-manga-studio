// ═══════════════════════════════════════════════
//  仪表盘
// ═══════════════════════════════════════════════
function renderDashboard() {
  const s = State.stats;
  const recentEps = State.episodes.slice(0,6);

  document.getElementById("mainContent").innerHTML = `
    <!-- 统计卡片 -->
    <div class="grid-4 mb-16">
      <div class="stat-card">
        <div class="stat-label">已孵化IP</div>
        <div class="stat-value" style="color:var(--primary)">
          ${s.ip_count||0}
          <span style="font-size:14px;color:var(--text-dim)"> / 10</span>
        </div>
        <div class="stat-sub">角色IP总数</div>
        <div class="stat-icon">🎭</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已生产剧集</div>
        <div class="stat-value" style="color:var(--accent)">
          ${s.episode_count||0}
        </div>
        <div class="stat-sub">今日 ${s.today_episodes||0} 集</div>
        <div class="stat-icon">🎬</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">平均质检分</div>
        <div class="stat-value" style="color:var(--success)">
          ${((s.avg_qc_score||0)*100).toFixed(1)}
          <span style="font-size:14px">分</span>
        </div>
        <div class="stat-sub">通过率 ${s.pass_rate||0}%</div>
        <div class="stat-icon">🔍</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">本月成本</div>
        <div class="stat-value" style="color:var(--warning)">
          $${(s.total_cost_usd||0).toFixed(2)}
        </div>
        <div class="stat-sub">≈ ¥${((s.total_cost_usd||0)*7.2).toFixed(2)}</div>
        <div class="stat-icon">💰</div>
      </div>
    </div>

    <!-- 最近剧集 -->
    <div class="section-header">
      <div class="section-title">最近生产</div>
      <div class="section-link" onclick="navigate('library')">查看全部 →</div>
    </div>
    <div class="grid-3">
      ${recentEps.length
        ? recentEps.map(ep => renderEpisodeCard(ep)).join("")
        : `<div class="empty-state" style="grid-column:1/-1">
             <div class="empty-icon">🎬</div>
             <div>暂无剧集，去生产中心创建第一集</div>
           </div>`
      }
    </div>

    ${State.ips.length ? `
    <!-- IP概览 -->
    <hr class="divider">
    <div class="section-header">
      <div class="section-title">IP概览</div>
      <div class="section-link" onclick="navigate('ip-manager')">管理IP →</div>
    </div>
    <div class="grid-4">
      ${State.ips.map(ip => `
        <div class="ip-card" onclick="navigate('ip-manager')">
          <div class="ip-avatar">🎭</div>
          <div class="ip-name">${ip.name}</div>
          <div class="ip-meta">${ip.world?.genre||""} · ${ip.world?.tone||""}</div>
          <div class="ip-stats">
            <span>🎬 ${ip.episode_count||0}集</span>
          </div>
        </div>
      `).join("")}
    </div>` : ""}
  `;
}

// ⚠️ renderEpisodeCard() 定义在 library.js 中，被本文件依赖