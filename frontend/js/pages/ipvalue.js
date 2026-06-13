async function renderIpValue() {
  const tb = document.getElementById("topbarActions");
  tb.innerHTML = `
    <button class="btn btn-ghost" onclick="renderIpValue()">🔄 刷新</button>
  `;

  // 加载所有IP的价值评估状态
  const [valueRes] = await Promise.all([
    fetch("/api/ipvalue/status").then(r => r.json())
  ]);

  const c = document.getElementById("mainContent");

  if (!State.ips.length) {
    c.innerHTML = `<div class="empty-state">
      <div class="empty-icon">💎</div>
      <div>暂无IP，请先创建角色</div>
    </div>`;
    return;
  }

  c.innerHTML = `
    <!-- 漏斗概览 -->
    <div class="card mb-16" style="background:linear-gradient(135deg,
      rgba(124,92,252,0.08),rgba(252,92,125,0.05))">
      <div class="bold mb-16">🔽 IP孵化漏斗</div>
      <div style="display:flex;align-items:center;gap:0">
        ${renderFunnelStep("全部IP",    State.ips.length,     "#7c5cfc", "100%")}
        ${renderFunnelArrow()}
        ${renderFunnelStep("初筛通过",
          State.ips.filter(ip =>
            valueRes[ip.ip_id]?.auto_screen?.passed
          ).length, "#9c7cff", "80%")}
        ${renderFunnelArrow()}
        ${renderFunnelStep("人工通过",
          State.ips.filter(ip =>
            valueRes[ip.ip_id]?.human_review?.decision === "pass"
          ).length, "#fc7c9c", "65%")}
        ${renderFunnelArrow()}
        ${renderFunnelStep("市场验证",
          State.ips.filter(ip =>
            valueRes[ip.ip_id]?.market_validation
          ).length, "#fc5c7d", "50%")}
        ${renderFunnelArrow()}
        ${renderFunnelStep("正式立项",
          State.ips.filter(ip =>
            valueRes[ip.ip_id]?.decided?.decision === "INCUBATE"
          ).length, "#f0a500", "35%")}
      </div>
    </div>

    <!-- IP卡片列表 -->
    <div style="display:flex;flex-direction:column;gap:16px">
      ${State.ips.map(ip =>
        renderIpValueCard(ip, valueRes[ip.ip_id] || {})
      ).join("")}
    </div>
  `;
}

function renderFunnelStep(label, count, color, width) {
  return `
    <div style="flex:1;text-align:center">
      <div style="
        background:${color}22;border:1px solid ${color}44;
        border-radius:8px;padding:12px 8px;
        clip-path:polygon(0 0,100% 0,${width} 100%,
          ${100-parseFloat(width)}% 100%);
        min-height:70px;display:flex;flex-direction:column;
        align-items:center;justify-content:center
      ">
        <div style="font-size:22px;font-weight:700;color:${color}">${count}</div>
        <div style="font-size:11px;color:var(--text-sub)">${label}</div>
      </div>
    </div>
  `;
}

function renderFunnelArrow() {
  return `<div style="color:var(--text-dim);font-size:18px;
    padding:0 4px;align-self:center">›</div>`;
}

function renderIpValueCard(ip, valueStatus) {
  const autoScreen   = valueStatus.auto_screen   || null;
  const humanReview  = valueStatus.human_review  || null;
  const marketVal    = valueStatus.market_validation || null;
  const decision     = valueStatus.decided       || null;

  const DECISION_MAP = {
    INCUBATE: { label:"✅ 正式立项", color:"var(--success)",
                bg:"rgba(76,175,130,0.08)", border:"var(--success)" },
    OBSERVE:  { label:"👁 继续观察", color:"var(--warning)",
                bg:"rgba(240,165,0,0.08)",  border:"var(--warning)" },
    ABANDON:  { label:"🗑 建议放弃", color:"var(--error)",
                bg:"rgba(252,92,92,0.08)",  border:"var(--error)"   },
  };

  const dec   = decision ? DECISION_MAP[decision.decision] : null;
  const cardBorder = dec?.border || "var(--border)";
  const cardBg     = dec?.bg     || "var(--bg-card)";

  return `
    <div style="background:${cardBg};border:1px solid ${cardBorder};
                border-radius:var(--radius);padding:20px"
         id="ipvalueCard_${ip.ip_id}">

      <!-- 头部 -->
      <div style="display:flex;justify-content:space-between;
                  align-items:flex-start;margin-bottom:16px">
        <div style="display:flex;gap:12px;align-items:center">
          <div style="
            width:48px;height:48px;border-radius:10px;
            background:linear-gradient(135deg,var(--primary-dim),var(--primary));
            display:flex;align-items:center;justify-content:center;font-size:22px
          ">🎭</div>
          <div>
            <div class="bold" style="font-size:16px">${ip.name}</div>
            <div class="text-dim" style="font-size:11px">${ip.ip_id}</div>
          </div>
        </div>
        ${dec ? `
          <div style="color:${dec.color};font-weight:600;font-size:14px">
            ${dec.label}
          </div>` : `
          <div class="text-dim" style="font-size:12px">评估中</div>`
        }
      </div>

      <!-- 三层进度 -->
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;
                  margin-bottom:16px">
        ${renderLayerCard(
          "Layer 1 · 自动初筛",
          autoScreen,
          () => triggerAutoScreen(ip.ip_id),
          "🤖"
        )}
        ${renderLayerCard(
          "Layer 2 · 人工复审",
          humanReview,
          () => openHumanReviewModal(ip.ip_id),
          "👤",
          !autoScreen?.passed
        )}
        ${renderLayerCard(
          "Layer 3 · 市场验证",
          marketVal,
          () => openMarketDataModal(ip.ip_id),
          "📊",
          humanReview?.decision !== "pass"
        )}
      </div>

      <!-- 决策区 -->
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div style="font-size:12px;color:var(--text-dim)">
          ${decision
            ? `综合分：<span style="color:${dec?.color};font-weight:600">
               ${(decision.composite_score*100).toFixed(1)}分</span>
               · ${decision.reason}`
            : "完成三层评估后可生成立项决策"
          }
        </div>
        <div style="display:flex;gap:8px">
          ${marketVal ? `
            <button class="btn btn-primary" style="font-size:12px"
              onclick="triggerDecision('${ip.ip_id}')">
              ⚡ 生成决策
            </button>` : ""}
          ${decision ? `
            <button class="btn btn-ghost" style="font-size:12px"
              onclick="openDecisionDetail('${ip.ip_id}')">
              📋 查看详情
            </button>` : ""}
        </div>
      </div>

      <!-- 决策行动列表 -->
      ${decision?.next_actions?.length ? `
        <div style="margin-top:14px;padding-top:14px;
                    border-top:1px solid var(--border)">
          <div style="font-size:12px;color:var(--text-sub);
                      margin-bottom:8px">📌 建议行动</div>
          <div style="display:flex;flex-direction:column;gap:4px">
            ${decision.next_actions.map(a => `
              <div style="font-size:12px;color:var(--text-sub);
                          display:flex;gap:8px;align-items:center">
                <span style="color:var(--primary)">›</span>${a}
              </div>
            `).join("")}
          </div>
        </div>` : ""}
    </div>
  `;
}

function renderLayerCard(title, data, action, icon, disabled = false) {
  const hasData  = !!data;
  const passed   = data?.passed !== undefined
    ? data.passed
    : (data?.decision === "pass");
  const score    = data?.weighted_score;

  return `
    <div style="background:var(--bg-hover);border-radius:8px;padding:12px;
                border:1px solid ${hasData
                  ? (passed ? "var(--success)" : "var(--warning)")
                  : "var(--border)"}">
      <div style="display:flex;justify-content:space-between;
                  align-items:center;margin-bottom:8px">
        <div style="font-size:11px;color:var(--text-dim)">${icon} ${title}</div>
        ${hasData ? `
          <span style="font-size:11px;color:${passed?"var(--success)":"var(--warning)"}">
            ${passed ? "✅" : "⚠️"}
          </span>` : ""}
      </div>

      ${hasData ? `
        <div style="font-size:22px;font-weight:700;
                    color:${passed?"var(--success)":"var(--warning)"};
                    margin-bottom:4px">
          ${score != null ? (score*100).toFixed(0) : "—"}
          <span style="font-size:12px">分</span>
        </div>
        <div style="font-size:10px;color:var(--text-dim)">
          ${data.evaluated_at?.slice(0,10) ||
            data.reviewed_at?.slice(0,10)  ||
            data.validated_at?.slice(0,10) || ""}
        </div>` : `
        <div class="text-dim" style="font-size:12px;margin-bottom:8px">
          未评估
        </div>`
      }

      <button
        class="btn ${hasData?"btn-ghost":"btn-primary"}"
        style="width:100%;font-size:11px;margin-top:8px;padding:5px"
        onclick="${disabled ? '' : `(${action})()`}"
        ${disabled ? "disabled" : ""}
      >
        ${disabled ? "🔒 需先完成上一层" :
          hasData ? "🔄 重新评估" : "▶ 开始评估"}
      </button>
    </div>
  `;
}

// ── 操作函数 ──────────────────────────────────

async function triggerAutoScreen(ipId) {
  showToast("自动初筛已启动...", "info");
  await fetch(`/api/ipvalue/auto-screen/${ipId}`, { method: "POST" });
  // 延迟5秒后刷新（等待LLM响应）
  setTimeout(() => renderIpValue(), 5000);
}

async function triggerDecision(ipId) {
  const res  = await fetch(`/api/ipvalue/decide/${ipId}`, { method: "POST" });
  const data = await res.json();
  showToast(`决策：${data.decision} · ${(data.composite_score*100).toFixed(0)}分`, "success");
  await renderIpValue();
}

// ── 人工复审弹窗 ──────────────────────────────

function openHumanReviewModal(ipId) {
  const ip = State.ips.find(i => i.ip_id === ipId);
  document.getElementById("modalTitle").textContent = `人工复审 · ${ip?.name || ipId}`;
  document.getElementById("modalMeta").textContent  = "Layer 2 · 四维评分";
  document.getElementById("videoPlayer").style.display = "none";

  document.getElementById("modalInfo").innerHTML = `
    <div style="padding:4px 0">
      <div style="margin-bottom:16px;font-size:13px;color:var(--text-sub)">
        请从以下四个维度为IP打分（0~10分）：
      </div>

      ${["角色魅力","商业潜力","内容质量","受众匹配"].map(dim => `
        <div style="margin-bottom:14px">
          <div style="display:flex;justify-content:space-between;
                      margin-bottom:6px;font-size:13px">
            <span>${dim}</span>
            <span id="score_label_${dim}"
                  style="color:var(--primary);font-weight:600">5</span>
          </div>
          <input type="range" min="0" max="10" value="5" step="0.5"
            style="width:100%;accent-color:var(--primary)"
            id="score_${dim}"
            oninput="document.getElementById('score_label_${dim}').textContent=this.value">
        </div>
      `).join("")}

      <div style="margin-bottom:14px">
        <div style="font-size:13px;margin-bottom:6px">复审意见</div>
        <textarea class="form-input" rows="3" id="reviewComments"
          placeholder="角色魅力突出，建议加强市场投放..."
          style="resize:vertical"></textarea>
      </div>

      <div style="margin-bottom:14px">
        <div style="font-size:13px;margin-bottom:8px">最终判断</div>
        <div style="display:flex;gap:8px">
          ${[["pass","✅ 通过","var(--success)"],
             ["observe","👁 观察","var(--warning)"],
             ["reject","❌ 否决","var(--error)"]].map(([val,label,color]) => `
            <label style="flex:1;cursor:pointer">
              <input type="radio" name="reviewDecision"
                value="${val}" ${val==="pass"?"checked":""} style="display:none">
              <div style="
                text-align:center;padding:10px;border-radius:7px;
                border:1px solid ${color}33;background:${color}11;
                color:${color};font-size:13px;cursor:pointer;
                transition:all 0.15s
              " onclick="this.parentElement.querySelector('input').checked=true;
                          highlightDecision(this,'${color}')">
                ${label}
              </div>
            </label>
          `).join("")}
        </div>
      </div>

      <button class="btn btn-primary" style="width:100%;padding:12px"
        onclick="submitHumanReview('${ipId}')">
        提交复审结果
      </button>
    </div>
  `;

  document.getElementById("videoModal").classList.add("show");
}

function highlightDecision(el, color) {
  document.querySelectorAll("[name=reviewDecision]").forEach(inp => {
    const div = inp.nextElementSibling;
    if (div) {
      div.style.background = "";
      div.style.borderWidth = "1px";
    }
  });
  el.style.background    = color + "22";
  el.style.borderWidth   = "2px";
}

async function submitHumanReview(ipId) {
  const dims = ["角色魅力","商业潜力","内容质量","受众匹配"];
  const scores = {};
  dims.forEach(d => {
    scores[d] = parseFloat(document.getElementById(`score_${d}`)?.value || 5) / 10;
  });
  const comments = document.getElementById("reviewComments")?.value || "";
  const decision = document.querySelector("[name=reviewDecision]:checked")?.value || "pass";

  const res  = await fetch(`/api/ipvalue/human-review/${ipId}`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ reviewer_scores: scores, comments, decision })
  });
  const data = await res.json();
  showToast(`复审已提交：${decision} · ${(data.weighted_score*100).toFixed(0)}分`, "success");
  closeModal();
  await renderIpValue();
}

// ── 市场数据录入弹窗 ──────────────────────────

function openMarketDataModal(ipId) {
  const ip = State.ips.find(i => i.ip_id === ipId);
  document.getElementById("modalTitle").textContent = `市场验证数据 · ${ip?.name || ipId}`;
  document.getElementById("modalMeta").textContent  = "Layer 3 · 填入实际投放数据";
  document.getElementById("videoPlayer").style.display = "none";

  document.getElementById("modalInfo").innerHTML = `
    <div style="padding:4px 0">
      <div class="grid-2" style="gap:12px;margin-bottom:16px">
        <div>
          <div class="form-label">投放平台</div>
          <select class="form-select" id="mktPlatform">
            <option>抖音</option><option>B站</option>
            <option>小红书</option><option>微博</option>
            <option>YouTube</option><option>其他</option>
          </select>
        </div>
        <div>
          <div class="form-label">投放集数</div>
          <input class="form-input" type="number" id="mktEpisodes"
            value="5" min="1">
        </div>
      </div>

      <div style="background:var(--bg-hover);border-radius:8px;
                  padding:14px;margin-bottom:16px">
        <div class="bold" style="margin-bottom:12px;font-size:13px">
          📊 核心指标
        </div>
        <div class="grid-2" style="gap:10px">
          ${[
            ["total_views",           "总播放量",       "10000", "次"],
            ["avg_completion_rate",   "平均完播率",      "0.65",  "(0~1)"],
            ["like_count",            "点赞数",          "800",   "个"],
            ["comment_count",         "评论数",          "100",   "条"],
            ["share_count",           "分享数",          "150",   "次"],
            ["return_viewers",        "回访率",          "0.40",  "(0~1)"]
          ].map(([id, label, placeholder, unit]) => `
            <div>
              <div class="form-label">${label}
                <span class="text-dim">${unit}</span>
              </div>
              <input class="form-input" type="number"
                id="mkt_${id}" placeholder="${placeholder}" step="any">
            </div>
          `).join("")}
        </div>
      </div>

      <div style="margin-bottom:16px">
        <div class="form-label">代表性评论（每行一条，用于情感分析）</div>
        <textarea class="form-input" rows="4" id="mktComments"
          placeholder="太萌了哈哈哈&#10;求更新！&#10;这个角色好像我朋友&#10;每天必看"
          style="resize:vertical"></textarea>
      </div>

      <button class="btn btn-primary" style="width:100%;padding:12px"
        onclick="submitMarketData('${ipId}')">
        提交市场数据
      </button>
    </div>
  `;

  document.getElementById("videoModal").classList.add("show");
}

async function submitMarketData(ipId) {
  const metrics = {
    total_views:           parseFloat(document.getElementById("mkt_total_views")?.value || 0),
    avg_completion_rate:   parseFloat(document.getElementById("mkt_avg_completion_rate")?.value || 0),
    like_count:            parseFloat(document.getElementById("mkt_like_count")?.value || 0),
    comment_count:         parseFloat(document.getElementById("mkt_comment_count")?.value || 0),
    share_count:           parseFloat(document.getElementById("mkt_share_count")?.value || 0),
    return_viewers:        parseFloat(document.getElementById("mkt_return_viewers")?.value || 0),
    comments_sample: (document.getElementById("mktComments")?.value || "")
                     .split("\n").filter(c => c.trim())
  };

  const res  = await fetch(`/api/ipvalue/market-data/${ipId}`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({
      platform:        document.getElementById("mktPlatform")?.value || "其他",
      sample_episodes: parseInt(document.getElementById("mktEpisodes")?.value || 5),
      raw_metrics:     metrics
    })
  });
  const data = await res.json();
  showToast(
    `市场验证完成：${(data.weighted_score*100).toFixed(0)}分`,
    data.passed ? "success" : "warning"
  );
  closeModal();
  await renderIpValue();
}

// ── 决策详情弹窗 ──────────────────────────────

async function openDecisionDetail(ipId) {
  const res    = await fetch(`/api/ipvalue/status/${ipId}`).then(r=>r.json());
  const auto   = res.auto_screen;
  const human  = res.human_review;
  const market = res.market_validation;
  const dec    = res.decided;
  const ip     = State.ips.find(i => i.ip_id === ipId);

  document.getElementById("modalTitle").textContent = `立项决策报告 · ${ip?.name}`;
  document.getElementById("modalMeta").textContent  = dec?.decided_at?.slice(0,19) || "";
  document.getElementById("videoPlayer").style.display = "none";

  const DECISION_COLORS = {
    INCUBATE:"var(--success)", OBSERVE:"var(--warning)", ABANDON:"var(--error)"
  };
  const DECISION_LABELS = {
    INCUBATE:"✅ 正式立项", OBSERVE:"👁 继续观察", ABANDON:"🗑 建议放弃"
  };

  document.getElementById("modalInfo").innerHTML = `
    <div style="text-align:center;padding:20px 0">
      <div style="font-size:48px;margin-bottom:8px">
        ${dec?.decision==="INCUBATE"?"🏆":dec?.decision==="OBSERVE"?"🔭":"💔"}
      </div>
      <div style="font-size:24px;font-weight:700;
                  color:${DECISION_COLORS[dec?.decision]||"var(--text-main)"}">
        ${DECISION_LABELS[dec?.decision]||"评估中"}
      </div>
      <div style="font-size:13px;color:var(--text-sub);margin-top:8px">
        ${dec?.reason || ""}
      </div>
    </div>

    <!-- 三层得分 -->
    <div class="grid-3" style="gap:10px;margin-bottom:16px">
      ${[
        ["🤖 自动初筛", auto?.weighted_score, auto?.passed],
        ["👤 人工复审", human?.weighted_score, human?.decision==="pass"],
        ["📊 市场验证", market?.weighted_score, market?.passed]
      ].map(([label, score, passed]) => `
        <div style="background:var(--bg-hover);border-radius:8px;
                    padding:12px;text-align:center">
          <div class="text-dim" style="font-size:11px;margin-bottom:6px">
            ${label}
          </div>
          <div style="font-size:24px;font-weight:700;
                      color:${passed?"var(--success)":"var(--text-dim)"}">
            ${score != null ? (score*100).toFixed(0) : "—"}
          </div>
          <div style="font-size:11px;color:${passed?"var(--success)":"var(--warning)"}">
            ${score != null ? (passed?"通过":"未通过") : "未评估"}
          </div>
        </div>
      `).join("")}
    </div>

    <!-- 综合分 -->
    <div style="background:var(--bg-hover);border-radius:8px;padding:14px;
                margin-bottom:16px;text-align:center">
      <div class="text-dim" style="font-size:12px;margin-bottom:4px">综合得分</div>
      <div style="font-size:40px;font-weight:700;
                  color:${DECISION_COLORS[dec?.decision]||"var(--text-main)"}">
        ${dec?.composite_score != null
          ? (dec.composite_score*100).toFixed(1) : "—"}
      </div>
    </div>

    <!-- 行动列表 -->
    ${dec?.next_actions?.length ? `
      <div style="margin-bottom:16px">
        <div class="bold" style="margin-bottom:10px;font-size:13px">
          📌 建议行动
        </div>
        ${dec.next_actions.map((a,i) => `
          <div style="display:flex;gap:10px;align-items:flex-start;
                      padding:8px 0;border-bottom:1px solid var(--border)">
            <div style="
              min-width:22px;height:22px;border-radius:50%;
              background:var(--primary-dim);color:var(--primary);
              display:flex;align-items:center;justify-content:center;
              font-size:11px;font-weight:600
            ">${i+1}</div>
            <div style="font-size:13px;color:var(--text-sub)">${a}</div>
          </div>
        `).join("")}
      </div>` : ""}

    <!-- 优势/劣势（初筛数据）-->
    ${auto ? `
      <div class="grid-2" style="gap:10px">
        <div>
          <div class="bold" style="font-size:12px;
            color:var(--success);margin-bottom:8px">✅ 优势</div>
          ${(auto.strengths||[]).map(s => `
            <div style="font-size:12px;color:var(--text-sub);
                        padding:3px 0">· ${s}</div>`).join("")}
        </div>
        <div>
          <div class="bold" style="font-size:12px;
            color:var(--warning);margin-bottom:8px">⚠️ 待改进</div>
          ${(auto.weaknesses||[]).map(w => `
            <div style="font-size:12px;color:var(--text-sub);
                        padding:3px 0">· ${w}</div>`).join("")}
        </div>
      </div>` : ""}
  `;

  document.getElementById("videoModal").classList.add("show");
}