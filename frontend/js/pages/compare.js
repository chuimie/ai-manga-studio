async function renderCompare() {
  const res      = await fetch("/api/compare/all").then(r => r.json());
  const analytics= res.analytics || [];

  document.getElementById("mainContent").innerHTML = `
    ${analytics.length < 2 ? `
      <div class="empty-state">
        <div class="empty-icon">📱</div>
        <div style="font-size:16px;font-weight:600;margin-bottom:8px">
          需要至少2个IP才能对比
        </div>
        <div class="text-sub">去创建更多IP角色</div>
      </div>` : `

      <!-- 排行榜 -->
      <div class="section-header mb-16">
        <div class="section-title">🏳 IP综合排名</div>
      </div>

      <!-- 排名卡片 -->
      <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:24px">
        ${analytics.map((a, i) => renderRankCard(a, i)).join("")}
      </div>

      <!-- 雷达图（纯CSS/Canvas） -->
      <div class="grid-2">

        <!-- 维度对比表 -->
        <div class="card">
          <div class="bold mb-16">📳 维度横向对比</div>
          <div style="overflow-x:auto">
            <table style="width:100%;border-collapse:collapse;font-size:12px">
              <thead>
                <tr style="background:var(--bg-hover)">
                  <th style="${thStyle()}">IP</th>
                  <th style="${thStyle()}">质检均分</th>
                  <th style="${thStyle()}">通过率</th>
                  <th style="${thStyle()}">IP潜力</th>
                  <th style="${thStyle()}">市场分</th>
                  <th style="${thStyle()}">集数</th>
                  <th style="${thStyle()}">成本</th>
                </tr>
              </thead>
              <tbody>
                ${analytics.map(a => `
                  <tr style="border-bottom:1px solid var(--border)">
                    <td style="${tdStyle()};font-weight:500">${a.ip_name}</td>
                    <td style="${tdStyle()};color:${scoreColor(a.qc.overall)}">
                      ${(a.qc.overall*100).toFixed(0)}
                    </td>
                    <td style="${tdStyle()};color:${scoreColor(a.qc.pass_rate)}">
                      ${(a.qc.pass_rate*100).toFixed(0)}%
                    </td>
                    <td style="${tdStyle()};color:${scoreColor(a.value.auto_score)}">
                      ${a.value.auto_score?(a.value.auto_score*100).toFixed(0):"—"}
                    </td>
                    <td style="${tdStyle()};color:${scoreColor(a.value.market_score)}">
                      ${a.value.market_score?(a.value.market_score*100).toFixed(0):"—"}
                    </td>
                    <td style="${tdStyle()};color:var(--text-sub)">
                      ${a.production.episode_count}
                    </td>
                    <td style="${tdStyle()};color:var(--warning)">
                      $${a.production.cost_usd}
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>

        <!-- 五维雷达Canvas -->
        <div class="card">
          <div class="bold mb-16">🕩️ 五维雷达图</div>
          <canvas id="radarCanvas" width="320" height="320"
            style="display:block;margin:0 auto"></canvas>
        </div>
      </div>

      <!-- 质检趋势 -->
      <div class="card" style="margin-top:16px">
        <div class="bold mb-16">📲 质检分趋势</div>
        <canvas id="trendCanvas" width="800" height="200"
          style="width:100%;height:200px"></canvas>
      </div>
    `}
  `;

  if (analytics.length >= 2) {
    drawRadarChart(analytics);
    drawTrendChart(analytics);
  }
}

function renderRankCard(a, i) {
  const MEDALS = ["🥌","🥍","🥎"];
  const medal  = MEDALS[i] || `${i+1}.`;
  const DECISION_COLORS = {
    INCUBATE:"var(--success)", OBSERVE:"var(--warning)",
    ABANDON:"var(--error)",    PENDING:"var(--text-dim)"
  };
  const DECISION_LABELS = {
    INCUBATE:"✅ 立项", OBSERVE:"👗 观察",
    ABANDON:"🗏 放弃",  PENDING:"评估中"
  };
  const dec   = a.value.decision || "PENDING";

  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);
                border-radius:var(--radius);padding:16px;
                display:grid;grid-template-columns:40px 1fr repeat(5,80px) 120px;
                align-items:center;gap:12px">
      <div style="font-size:20px;text-align:center">${medal}</div>
      <div>
        <div class="bold">${a.ip_name}</div>
        <div class="text-dim" style="font-size:11px">${a.ip_id}</div>
      </div>

      ${[
        ["质检", a.qc.overall],
        ["通过率", a.qc.pass_rate],
        ["IP潜力", a.value.auto_score||0],
        ["市场", a.value.market_score||0],
        ["综合", a.composite_score||0]
      ].map(([label, val]) => `
        <div style="text-align:center">
          <div style="font-size:18px;font-weight:700;
                      color:${scoreColor(val)}">
            ${val ? (val*100).toFixed(0) : "—"}
          </div>
          <div class="text-dim" style="font-size:10px">${label}</div>
        </div>
      `).join("")}

      <div style="text-align:right">
        <div style="font-size:13px;font-weight:600;
                    color:${DECISION_COLORS[dec]}">
          ${DECISION_LABELS[dec]}
        </div>
        <div class="text-dim" style="font-size:11px;margin-top:2px">
          ${a.production.episode_count}集 ·
          ${a.qc.trend==="up"?"📱":a.qc.trend==="down"?"📲":"⏺️"}
        </div>
      </div>
    </div>
  `;
}

function drawRadarChart(analytics) {
  const canvas  = document.getElementById("radarCanvas");
  if (!canvas) return;
  const ctx     = canvas.getContext("2d");
  const cx      = 160, cy = 160, r = 120;
  const labels  = ["质检均分","通过率","IP潜力","市场表现","生产规模"];
  const n       = labels.length;
  const colors_ = ["#7c5cfc","#fc5c7d","#4caf82","#f0a500","#7cf0fc"];

  ctx.clearRect(0, 0, 320, 320);

  // 绘制网格
  for (let ring = 1; ring <= 5; ring++) {
    ctx.beginPath();
    ctx.strokeStyle = "#2a2a40";
    ctx.lineWidth   = 1;
    for (let i = 0; i <= n; i++) {
      const angle = (i * 2*Math.PI/n) - Math.PI/2;
      const rr    = r * ring / 5;
      const x     = cx + rr * Math.cos(angle);
      const y     = cy + rr * Math.sin(angle);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();
  }

  // 绘制轴线
  for (let i = 0; i < n; i++) {
    const angle = (i * 2*Math.PI/n) - Math.PI/2;
    ctx.beginPath();
    ctx.strokeStyle = "#3a3a60";
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + r * Math.cos(angle), cy + r * Math.sin(angle));
    ctx.stroke();

    // 标签
    const lx = cx + (r+20) * Math.cos(angle);
    const ly = cy + (r+20) * Math.sin(angle);
    ctx.fillStyle  = "#9090b0";
    ctx.font       = "11px sans-serif";
    ctx.textAlign  = "center";
    ctx.fillText(labels[i], lx, ly);
  }

  // 绘制每个IP的多边形
  analytics.slice(0,5).forEach((a, idx) => {
    const values = [
      a.qc.overall,
      a.qc.pass_rate,
      a.value.auto_score || 0,
      a.value.market_score || 0,
      Math.min(1, a.production.episode_count / 30)
    ];
    const color = colors_[idx];

    ctx.beginPath();
    values.forEach((v, i) => {
      const angle = (i * 2*Math.PI/n) - Math.PI/2;
      const rr    = r * v;
      const x     = cx + rr * Math.cos(angle);
      const y     = cy + rr * Math.sin(angle);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fillStyle   = color + "22";
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth   = 2;
    ctx.stroke();

    // 图例
    ctx.fillStyle  = color;
    ctx.fillRect(10, 10 + idx*18, 12, 12);
    ctx.fillStyle  = "#c0c0d8";
    ctx.font       = "11px sans-serif";
    ctx.textAlign  = "left";
    ctx.fillText(a.ip_name, 28, 21 + idx*18);
  });
}

function drawTrendChart(analytics) {
  const canvas = document.getElementById("trendCanvas");
  if (!canvas) return;
  const ctx    = canvas.getContext("2d");
  const W      = canvas.offsetWidth || 800;
  const H      = 200;
  canvas.width = W;

  ctx.clearRect(0, 0, W, H);

  const colors_ = ["#7c5cfc","#fc5c7d","#4caf82","#f0a500","#7cf0fc"];
  const pad     = { top:20, right:40, bottom:30, left:40 };

  // 坐标轴
  ctx.strokeStyle = "#2a2a40";
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, H-pad.bottom);
  ctx.lineTo(W-pad.right, H-pad.bottom);
  ctx.stroke();

  // Y轴刻度
  for (let v = 0; v <= 1; v += 0.2) {
    const y = H - pad.bottom - v*(H-pad.top-pad.bottom);
    ctx.fillStyle  = "#606080";
    ctx.font       = "10px sans-serif";
    ctx.textAlign  = "right";
    ctx.fillText((v*100).toFixed(0), pad.left-4, y+3);
    ctx.strokeStyle= "#1a1a2e";
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(W-pad.right, y);
    ctx.stroke();
  }

  // 每个IP的质检趋势线（模拟数据）
  analytics.slice(0,5).forEach((a, idx) => {
    const qcReports = [];
    const qcDir     = "./qc_reports";

    // 使用overall分数模拟趋势（实际从后端获取）
    const baseScore = a.qc.overall;
    const points    = Array.from({length:Math.max(5,a.production.episode_count)},
      (_,i) => Math.min(1, Math.max(0,
        baseScore + (Math.random()-0.5)*0.1
      ))
    );

    if (points.length < 2) return;

    const xStep = (W - pad.left - pad.right) / (points.length - 1);
    const color  = colors_[idx];

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth   = 2;

    points.forEach((v, i) => {
      const x = pad.left + i * xStep;
      const y = H - pad.bottom - v*(H-pad.top-pad.bottom);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
}