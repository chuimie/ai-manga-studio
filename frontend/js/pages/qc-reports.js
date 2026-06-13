function renderQcReports() {
  const c = document.getElementById("mainContent");
  if (!State.qcReports.length) {
    c.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <div style="font-size:16px;font-weight:600;margin-bottom:8px">暂无质检报告</div>
        <div class="text-sub">生产完成后自动生成</div>
      </div>`;
    return;
  }

  // 汇总统计
  const avg = State.qcReports.reduce((s,r)=>s+r.weighted_score,0) / State.qcReports.length;
  const passCount = State.qcReports.filter(r=>r.passed).length;

  c.innerHTML = `
    <!-- 汇总 -->
    <div class="grid-3 mb-16">
      <div class="stat-card">
        <div class="stat-label">报告总数</div>
        <div class="stat-value">${State.qcReports.length}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">通过率</div>
        <div class="stat-value text-success">
          ${(passCount/State.qcReports.length*100).toFixed(0)}%
        </div>
        <div class="stat-sub">${passCount}/${State.qcReports.length} 通过</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">平均得分</div>
        <div class="stat-value" style="color:var(--primary)">
          ${(avg*100).toFixed(1)}
          <span style="font-size:14px">分</span>
        </div>
      </div>
    </div>

    <!-- 报告列表 -->
    ${State.qcReports.map(r => renderQcCard(r)).join("")}
  `;
}

function renderQcCard(r) {
  const score   = r.weighted_score;
  const passed  = r.passed;
  const dims    = r.scores || {};
  const weights = {
    "角色一致性":0.35, "画面质量":0.25,
    "情绪吻合度":0.20, "叙事连贯性":0.15, "节奏合理性":0.05
  };

  const bars = Object.entries(dims).map(([k,v]) => {
    const pct   = (v*100).toFixed(0);
    const cls   = v>=0.85 ? "bar-good" : v>=0.70 ? "bar-medium" : "bar-poor";
    const wt    = weights[k] ? `(${(weights[k]*100).toFixed(0)}%)` : "";
    return `
      <div class="qc-bar-row">
        <div class="qc-bar-label">${k} <span class="text-dim">${wt}</span></div>
        <div class="qc-bar-track">
          <div class="qc-bar-fill ${cls}" style="width:${pct}%"></div>
        </div>
        <div class="qc-bar-val">${pct}分</div>
      </div>
    `;
  }).join("");

  return `
    <div class="qc-report-card">
      <div class="qc-header">
        <div>
          <div style="font-size:14px;font-weight:600">${r.ip_id} 第${r.episode_num}集</div>
          <div class="text-dim" style="font-size:12px">${r.ep_id || ""}</div>
          ${r.failed_items?.length
            ? `<div style="font-size:12px;color:var(--warning);margin-top:4px">
                 待改进：${r.failed_items.join(" · ")}
               </div>` : ""}
        </div>
        <div class="text-right">
          <div class="qc-score-big ${passed?"score-pass":"score-fail"}">
            ${(score*100).toFixed(0)}
          </div>
          <div class="${passed?"text-success":"text-warning"}" style="font-size:12px">
            ${passed ? "✅ 通过" : "⚠️ 需迭代"}
          </div>
        </div>
      </div>
      <div class="qc-bars">${bars}</div>
    </div>
  `;
}