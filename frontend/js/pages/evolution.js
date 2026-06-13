async function renderEvolution() {
  const tb = document.getElementById("topbarActions");
  tb.innerHTML = `
    <button class="btn btn-primary" style="font-size:12px"
      onclick="triggerEvolve()">🧬 执行进化</button>
    <button class="btn btn-ghost" style="font-size:12px"
      onclick="resetWeights()">🔄 重置权重</button>
  `;

  document.getElementById("mainContent").innerHTML = `
    <!-- IP选择 -->
    <div class="card mb-16" style="display:flex;align-items:center;gap:16px;
         padding:12px 20px;flex-wrap:wrap">
      <label style="font-size:13px;font-weight:500;color:var(--text-sub)">
        选择IP：
      </label>
      <select class="form-select" id="evoIpSel"
        style="width:240px"
        onchange="loadEvolutionData()">
        ${State.ips.map(ip => `
          <option value="${ip.ip_id}">${ip.name}（${ip.ip_id}）</option>
        `).join("")}
      </select>

      <div id="weightsDisplay" style="flex:1;min-width:300px;"></div>

      <div id="perfSummary" style="min-width:200px;"></div>
    </div>

    <div class="card mb-16" id="insightsCard">
      <div style="display:flex;justify-content:space-between;
                  align-items:center;margin-bottom:14px">
        <div class="bold">🔳 策略洞察</div>
        <button class="btn btn-ghost" style="font-size:12px"
          onclick="loadInsights()">刷新分析</button>
      </div>
      <div id="insightsContent" class="text-dim"
           style="font-size:13px">点击「刷新分析」获取AI洞察</div>
    </div>

    <div class="grid-2" style="gap:16px;margin-bottom:16px">

      <!-- 左下：手动编辑权重 -->
      <div class="card">
        <div class="bold mb-16">🛠️ 手动调权</div>
        <div id="weightEditor">加载中...</div>
      </div>

      <!-- 右下：A/B测试 -->
      <div class="card">
        <div style="display:flex;justify-content:space-between;
                    align-items:center;margin-bottom:14px">
          <div class="bold">🔩 A/B 测试</div>
          <button class="btn btn-primary" style="font-size:12px"
            onclick="openABTestModal()">+ 新建</button>
        </div>
        <div id="abTestList">加载中...</div>
      </div>
    </div>

    <!-- 底部：进化历史 -->
    <div class="card">
      <div class="bold mb-16">📱 进化历史</div>
      <canvas id="evolutionCanvas"
        style="width:100%;height:180px"></canvas>
      <div id="evolutionLog"
           style="margin-top:14px;max-height:200px;overflow-y:auto">
      </div>
    </div>
  `;

  await loadEvolutionData();
}

async function loadEvolutionData() {
  const ipId = document.getElementById("evoIpSel")?.value
             || State.ips[0]?.ip_id;
  if (!ipId) return;

  const [weightsRes, perfRes, histRes, abRes] = await Promise.all([
    fetch(`/api/evolution/weights/${ipId}`).then(r=>r.json()),
    fetch(`/api/evolution/performance/${ipId}`).then(r=>r.json()),
    fetch(`/api/evolution/history/${ipId}`).then(r=>r.json()),
    fetch(`/api/evolution/abtests?ip_id=${ipId}`).then(r=>r.json())
  ]);

  renderWeightsDisplay(weightsRes.weights);
  renderPerfSummary(perfRes.summary);
  renderWeightEditor(ipId, weightsRes.weights);
  renderABTestList(abRes.tests || []);
  renderEvolutionHistory(histRes.history || []);
}

function renderWeightsDisplay(weights) {
  const el = document.getElementById("weightsDisplay");
  if (!el || !weights) return;

  const DIM_LABELS = {
    genre:"题材", tone:"基调",
    narrative:"叙事", pacing:"节奏"
  };
  const COLORS = ["#7c5cfc","#fc5c7d","#4caf82","#f0a500"];

  el.innerHTML = Object.entries(weights).map(([dim, opts], di) => `
    <div style="margin-bottom:14px">
      <div style="font-size:12px;color:var(--text-sub);margin-bottom:6px;
                  font-weight:600">${DIM_LABELS[dim]||dim}</div>
      ${Object.entries(opts)
          .sort((a,b) => b[1]-a[1])
          .map(([opt, w]) => `
        <div style="display:flex;align-items:center;
                    gap:8px;margin-bottom:4px">
          <div style="width:60px;font-size:11px;
                      color:var(--text-dim);text-align:right">
            ${opt}
          </div>
          <div style="flex:1;background:var(--bg-hover);
                      border-radius:3px;height:14px;overflow:hidden">
            <div style="width:${(w*100).toFixed(1)}%;height:100%;
                        background:${COLORS[di]};
                        border-radius:3px;transition:width 0.5s">
            </div>
          </div>
          <div style="width:36px;font-size:11px;
                      color:${COLORS[di]};font-weight:600">
            ${(w*100).toFixed(0)}%
          </div>
        </div>
      `).join("")}
    </div>
  `).join("");
}

function renderPerfSummary(summary) {
  const el = document.getElementById("perfSummary");
  if (!el) return;
  if (!summary || !summary.total) {
    el.innerHTML = `<div class="text-dim" style="text-align:center;
      padding:20px">暂无表现数据<br>
      <span style="font-size:11px">生产并录入市场数据后自动分析</span></div>`;
    return;
  }

  const TREND_MAP = {
    up:     {icon:"📱", color:"var(--success)", label:"上升"},
    down:   {icon:"📲", color:"var(--error)",   label:"下降"},
    stable: {icon:"⏺️", color:"var(--warning)", label:"平稳"}
  };
  const trend = TREND_MAP[summary.trend] || TREND_MAP.stable;

  el.innerHTML = `
    <div class="grid-2" style="gap:8px;margin-bottom:12px">
      ${[
        ["样本集数",  summary.total,                     "var(--primary)"],
        ["平均得分",  (summary.avg_score*100).toFixed(1)+"分","var(--success)"],
        ["最高得分",  (summary.best_score*100).toFixed(1)+"分","var(--warning)"],
        ["趋势",      `${trend.icon} ${trend.label}`,    trend.color]
      ].map(([k,v,c]) => `
        <div style="background:var(--bg-hover);border-radius:7px;padding:10px">
          <div class="text-dim" style="font-size:10px;margin-bottom:3px">${k}</div>
          <div style="font-size:16px;font-weight:700;color:${c}">${v}</div>
        </div>
      `).join("")}
    </div>

    ${summary.best_combo ? `
      <div style="margin-bottom:8px">
        <div class="text-dim" style="font-size:11px;margin-bottom:4px">
          🏳 最优组合
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          ${Object.entries(summary.best_combo).map(([k,v]) => `
            <span style="background:rgba(76,175,130,0.15);
                         color:var(--success);padding:2px 8px;
                         border-radius:10px;font-size:11px">
              ${v}
            </span>
          `).join("")}
        </div>
      </div>` : ""}

    ${summary.worst_combo ? `
      <div>
        <div class="text-dim" style="font-size:11px;margin-bottom:4px">
          ⚠️ 低效组合
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          ${Object.entries(summary.worst_combo).map(([k,v]) => `
            <span style="background:rgba(252,92,92,0.1);
                         color:var(--error);padding:2px 8px;
                         border-radius:10px;font-size:11px">
              ${v}
            </span>
          `).join("")}
        </div>
      </div>` : ""}
  `;
}

function renderWeightEditor(ipId, weights) {
  const el = document.getElementById("weightEditor");
  if (!el) return;

  const DIM_LABELS = {
    genre:"题材", tone:"基调",
    narrative:"叙事", pacing:"节奏"
  };

  el.innerHTML = `
    <div style="font-size:12px;color:var(--text-dim);margin-bottom:12px">
      拖动滑块手动调整权重，调整后点击保存
    </div>
    ${Object.entries(weights).map(([dim, opts]) => `
      <div style="margin-bottom:14px">
        <div style="font-size:12px;color:var(--text-sub);
                    font-weight:600;margin-bottom:6px">
          ${DIM_LABELS[dim]||dim}
        </div>
        ${Object.entries(opts).map(([opt, w]) => `
          <div style="display:flex;align-items:center;
                      gap:8px;margin-bottom:6px">
            <div style="width:64px;font-size:11px;
                        color:var(--text-dim)">${opt}</div>
            <input type="range" min="5" max="70" step="1"
              value="${Math.round(w*100)}"
              style="flex:1;accent-color:var(--primary)"
              id="w_${dim}_${opt}"
              oninput="document.getElementById('wv_${dim}_${opt}')
                       .textContent=this.value+'%'">
            <div style="width:32px;font-size:11px;
                        color:var(--primary);text-align:right"
                 id="wv_${dim}_${opt}">
              ${Math.round(w*100)}%
            </div>
          </div>
        `).join("")}
      </div>
    `).join("")}
    <button class="btn btn-primary" style="width:100%;margin-top:8px"
      onclick="saveManualWeights('${ipId}')">
      💑 保存权重
    </button>
  `;
}

function renderABTestList(tests) {
  const el = document.getElementById("abTestList");
  if (!el) return;

  if (!tests.length) {
    el.innerHTML = `<div class="text-dim" style="text-align:center;
      padding:20px;font-size:13px">暂无A/B测试</div>`;
    return;
  }

  el.innerHTML = tests.slice(0,5).map(t => `
    <div style="background:var(--bg-hover);border-radius:8px;
                padding:12px;margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;
                  align-items:center;margin-bottom:8px">
        <div style="font-size:13px;font-weight:500">${t.test_name}</div>
        <span style="font-size:11px;padding:2px 8px;border-radius:10px;
          background:${t.status==='running'?'rgba(124,92,252,0.15)':
                       t.status==='concluded'?'rgba(76,175,130,0.15)':
                       'var(--bg-hover)'};
          color:${t.status==='running'?'var(--primary)':
                  t.status==='concluded'?'var(--success)':
                  'var(--text-dim)'}">
          ${t.status==='running'?'进行中':'已结束'}
        </span>
      </div>

      <div class="grid-2" style="gap:6px;font-size:12px">
        <div style="background:var(--bg-panel);border-radius:5px;padding:6px">
          <div class="text-dim" style="font-size:10px">变体A</div>
          <div style="color:var(--text-sub)">
            ${Object.values(t.variant_a?.config||{}).join("·")}
          </div>
          <div style="color:var(--primary)">
            ${t.variant_a?.scores?.length||0}集 /
            ${t.avg_a?(t.avg_a*100).toFixed(0)+"分":"待数据"}
          </div>
        </div>
        <div style="background:var(--bg-panel);border-radius:5px;padding:6px">
          <div class="text-dim" style="font-size:10px">变体B</div>
          <div style="color:var(--text-sub)">
            ${Object.values(t.variant_b?.config||{}).join("·")}
          </div>
          <div style="color:var(--accent)">
            ${t.variant_b?.scores?.length||0}集 /
            ${t.avg_b?(t.avg_b*100).toFixed(0)+"分":"待数据"}
          </div>
        </div>
      </div>

      ${t.winner ? `
        <div style="margin-top:8px;font-size:12px;
                    color:var(--success);font-weight:500">
          🏳 胜出：变体${t.winner.toUpperCase()}
        </div>` : `
        <button class="btn btn-ghost"
          style="width:100%;font-size:11px;margin-top:8px"
          onclick="concludeABTest('${t.test_id}')">
          结束并应用胜出方
        </button>`}
    </div>
  `).join("");
}

function renderEvolutionHistory(history) {
  const el = document.getElementById("evolutionLog");
  if (!el) return;

  el.innerHTML = history.map(h => `
    <div style="display:flex;gap:10px;padding:6px 0;
                border-bottom:1px solid var(--border);
                font-size:12px">
      <div class="text-dim" style="min-width:100px">
        ${h.timestamp?.slice(0,16)||""}
      </div>
      <div style="color:var(--primary)">${h.reason||"—"}</div>
    </div>
  `).join("") || `<div class="text-dim" style="text-align:center;
    padding:20px">暂无历史</div>`;
}

// ══════ 操作函数 ════════════════════════════════

async function triggerEvolve() {
  const ipId = document.getElementById("evoIpSel")?.value
             || State.ips[0]?.ip_id;
  if (!ipId) return;
  showToast("进化计算中...", "info");
  const res  = await fetch(`/api/evolution/evolve/${ipId}`,
    {method:"POST"}).then(r=>r.json());
  if (res.status === "evolved") {
    showToast(`✅ 进化完成！最大变化：${(res.max_change*100).toFixed(1)}%`,
              "success");
    await loadEvolutionData();
  } else {
    showToast(res.message || "数据不足", "warning");
  }
}

async function resetWeights() {
  const ipId = document.getElementById("evoIpSel")?.value
             || State.ips[0]?.ip_id;
  if (!confirm("重置所有风格权重为均等分布？")) return;
  await fetch(`/api/evolution/reset/${ipId}`, {method:"POST"});
  showToast("权重已重置", "info");
  await loadEvolutionData();
}

async function saveManualWeights(ipId) {
  const weights = {};
  for (const [dim, opts] of Object.entries({
    genre:     ["都市","玄幻","悬疑","爱情"],
    tone:      ["热血","治愈","黑暗","喜剧"],
    narrative: ["线性叙事","插叙","多视角","单场景深耕"],
    pacing:    ["快节奏","慢节奏","张弛交替","悬念递进"]
  })) {
    weights[dim] = {};
    let total    = 0;
    for (const opt of opts) {
      const val = parseInt(
        document.getElementById(`w_${dim}_${opt}`)?.value || 25
      );
      weights[dim][opt] = val;
      total += val;
    }
    // 归一化
    for (const opt of opts) {
      weights[dim][opt] = parseFloat(
        (weights[dim][opt] / total).toFixed(4)
      );
    }
  }
  await fetch(`/api/evolution/weights/${ipId}`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({weights})
  });
  showToast("权重已保存", "success");
  await loadEvolutionData();
}

async function loadInsights() {
  const ipId = document.getElementById("evoIpSel")?.value
             || State.ips[0]?.ip_id;
  const el   = document.getElementById("insightsContent");
  if (!el || !ipId) return;
  el.innerHTML = `<div class="spinner"></div>`;
  const data = await fetch(`/api/evolution/insights/${ipId}`)
    .then(r=>r.json());

  el.innerHTML = `
    <div class="grid-2" style="gap:12px">
      <div>
        <div style="font-size:12px;color:var(--success);
                    font-weight:600;margin-bottom:8px">
          ✅ 核心洞察
        </div>
        ${(data.insights||[]).map(i => `
          <div style="font-size:12px;color:var(--text-sub);
                      padding:4px 0;border-bottom:1px solid var(--border)">
            · ${i}
          </div>
        `).join("")}
      </div>
      <div>
        <div style="font-size:12px;color:var(--primary);
                    font-weight:600;margin-bottom:8px">
          💕 优化建议
        </div>
        ${(data.suggestions||[]).map(s => `
          <div style="font-size:12px;color:var(--text-sub);
                      padding:4px 0;border-bottom:1px solid var(--border)">
            · ${s}
          </div>
        `).join("")}
      </div>
    </div>
    ${data.avoid?.length ? `
      <div style="margin-top:12px;padding:10px;
                  background:rgba(252,92,92,0.08);
                  border-radius:6px;border-left:3px solid var(--error)">
        <div style="font-size:11px;color:var(--error);margin-bottom:4px">
          ⚠️ 建议规避
        </div>
        <div style="font-size:12px;color:var(--text-sub)">
          ${data.avoid.join(" · ")}
        </div>
      </div>` : ""}
    ${data.top_combo ? `
      <div style="margin-top:12px;padding:10px;
                  background:rgba(124,92,252,0.08);
                  border-radius:6px">
        <div class="text-dim" style="font-size:11px">当前最优组合</div>
        <div style="color:var(--primary);font-weight:600;
                    font-size:13px;margin-top:3px">
          ${data.top_combo}
        </div>
      </div>` : ""}
  `;
}

function openABTestModal() {
  const ipId = document.getElementById("evoIpSel")?.value
             || State.ips[0]?.ip_id;
  const OPTS = {
    genre:     ["都市","玄幻","悬疑","爱情"],
    tone:      ["热血","治愈","黑暗","喜剧"],
    pacing:    ["快节奏","慢节奏","张弛交替","悬念递进"]
  };

  document.getElementById("modalTitle").textContent = "创建A/B测试";
  document.getElementById("modalMeta").textContent  = ipId;
  document.getElementById("videoPlayer").style.display = "none";

  document.getElementById("modalInfo").innerHTML = `
    <div style="padding:4px 0">
      <div class="form-group">
        <label class="form-label">测试名称</label>
        <input class="form-input" id="abTestName"
          placeholder="例如：都市vs玄幻对比">
      </div>

      <div class="grid-2" style="gap:12px;margin-bottom:16px">
        ${["A","B"].map(v => `
          <div>
            <div style="font-size:13px;font-weight:600;
                        color:${v==="A"?"var(--primary)":"var(--accent)"};
                        margin-bottom:10px">变体${v}</div>
            ${Object.entries(OPTS).map(([dim, opts]) => `
              <div class="form-group">
                <label class="form-label">${
                  {genre:"题材",tone:"基调",pacing:"节奏"}[dim]||dim
                }</label>
                <select class="form-select" id="ab${v}_${dim}">
                  ${opts.map(o => `<option>${o}</option>`).join("")}
                </select>
              </div>
            `).join("")}
          </div>
        `).join("")}
      </div>

      <div class="form-group">
        <label class="form-label">每组测试集数</label>
        <input class="form-input" type="number" id="abEpCount"
          value="5" min="3" max="20">
      </div>

      <button class="btn btn-primary" style="width:100%;padding:12px"
        onclick="submitABTest('${ipId}')">
        🔩 创建A/B测试
      </button>
    </div>
  `;
  document.getElementById("videoModal").classList.add("show");
}

async function submitABTest(ipId) {
  const dims    = ["genre","tone","pacing"];
  const variantA = {}, variantB = {};
  dims.forEach(d => {
    variantA[d] = document.getElementById(`abA_${d}`)?.value;
    variantB[d] = document.getElementById(`abB_${d}`)?.value;
  });
  const testName = document.getElementById("abTestName")?.value
                 || "A/B测试";
  const epCount  = parseInt(
    document.getElementById("abEpCount")?.value || 5
  );

  await fetch(`/api/evolution/abtest/${ipId}`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({
      test_name: testName,
      variant_a: variantA,
      variant_b: variantB,
      episodes_per_variant: epCount
    })
  });
  showToast("A/B测试已创建", "success");
  closeModal();
  await loadEvolutionData();
}

async function concludeABTest(testId) {
  const res = await fetch(
    `/api/evolution/abtest/${testId}/conclude`,
    {method:"POST"}
  ).then(r=>r.json());
  showToast(
    `测试结束，胜出：变体${res.winner?.toUpperCase()}`,
    "success"
  );
  await loadEvolutionData();
}