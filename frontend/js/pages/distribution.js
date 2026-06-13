async function renderDistribution() {
  const histRes  = await fetch("/api/distribution/history").then(r=>r.json());
  const history  = histRes.history || [];
  const PLATFORMS= ["抖音","B站","小红书","微博","YouTube"];

  const tb = document.getElementById("topbarActions");
  tb.innerHTML = ``;

  document.getElementById("mainContent").innerHTML = `
    <div class="grid-2">

      <!-- 左：生成控制 -->
      <div>
        <div class="card mb-16">
          <div class="bold mb-16">➕ 生成发布素材</div>

          <div class="form-group">
            <label class="form-label">选择剧集</label>
            <select class="form-select" id="distEpSel">
              <option value="">-- 选择剧集 --</option>
              ${State.episodes?.map(ep => `
                <option value="${ep.ep_id}">
                  ${ep.ip_name} · ${ep.ep_id}
                </option>
              `).join("") || ""}
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">目标平台（可多选）</label>
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px">
              ${PLATFORMS.map(p => `
                <label style="display:flex;align-items:center;gap:6px;
                              cursor:pointer;font-size:13px;
                              background:var(--bg-hover);
                              padding:6px 12px;border-radius:20px;
                              border:1px solid var(--border)">
                  <input type="checkbox" value="${p}"
                    class="distPlatformCheck" checked>
                  ${p}
                </label>
              `).join("")}
            </div>
          </div>

          <button class="btn btn-primary" style="width:100%;padding:12px"
            onclick="generateDistribution()">
            ✅ 生成发布素材
          </button>
        </div>

        <!-- 历史记录 -->
        <div class="card">
          <div class="bold mb-16">📵 生成历史</div>
          ${history.length
            ? history.map(h => `
                <div style="padding:10px 0;border-bottom:1px solid var(--border);
                            cursor:pointer"
                     onclick="loadDistPackage('${h.ep_id}')">
                  <div style="display:flex;justify-content:space-between">
                    <div class="bold" style="font-size:13px">${h.ip_name}</div>
                    <div class="text-dim" style="font-size:11px">
                      ${h.generated_at?.slice(0,10)||""}
                    </div>
                  </div>
                  <div class="text-dim" style="font-size:11px;margin-top:2px">
                    ${h.ep_id} · ${h.platforms?.join(" / ")}
                  </div>
                </div>
              `).join("")
            : `<div class="text-dim" style="text-align:center;padding:20px">
                 暂无历史记录
               </div>`
          }
        </div>
      </div>

      <!-- 右：素材展示 -->
      <div id="distResultPanel">
        <div class="card" style="height:100%;display:flex;align-items:center;
             justify-content:center">
          <div style="text-align:center;color:var(--text-dim)">
            <div style="font-size:48px;opacity:0.3;margin-bottom:12px">📙</div>
            <div>选择剧集并点击生成，这里将展示各平台素材</div>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function generateDistribution() {
  const epId     = document.getElementById("distEpSel")?.value;
  if (!epId) { showToast("请先选择剧集", "error"); return; }

  const platforms = Array.from(
    document.querySelectorAll(".distPlatformCheck:checked")
  ).map(el => el.value);

  if (!platforms.length) { showToast("请至少选择一个平台", "error"); return; }

  showToast("素材生成中，请稍候...", "info");
  await fetch(`/api/distribution/generate/${epId}`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({platforms})
  });

  // 等待生成完成后加载
  setTimeout(() => loadDistPackage(epId), 6000);
}

async function loadDistPackage(epId) {
  const res  = await fetch(`/api/distribution/${epId}`);
  if (!res.ok) { showToast("素材未就绪，请稍后刷新", "warning"); return; }
  const pkg  = await res.json();

  const panel = document.getElementById("distResultPanel");
  if (!panel) return;

  const PLATFORM_ICONS = {
    "抖音":"📍","B站":"📵","小红书":"📃","微博":"😁","YouTube":"▶️"
  };

  panel.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:14px">

      <!-- 通用素材 -->
      ${pkg.common ? `
        <div class="card">
          <div class="bold mb-16">📑 通用素材</div>

          <!-- Slogan -->
          <div style="background:linear-gradient(135deg,var(--primary-dim),
               rgba(252,92,125,0.2));border-radius:8px;padding:14px;
               margin-bottom:12px;text-align:center">
            <div class="text-dim" style="font-size:11px;margin-bottom:4px">
              系列Slogan
            </div>
            <div style="font-size:18px;font-weight:700;color:var(--primary)">
              ${pkg.common.slogan || "—"}
            </div>
          </div>

          <!-- 系列简介 -->
          <div style="margin-bottom:12px">
            <div class="text-dim" style="font-size:11px;margin-bottom:6px">
              系列简介
            </div>
            <div style="background:var(--bg-hover);border-radius:6px;
                        padding:10px;font-size:13px;color:var(--text-sub)">
              ${pkg.common.series_intro || "—"}
            </div>
          </div>

          <!-- 金句卡片 -->
          ${pkg.common.quote_cards?.length ? `
            <div class="text-dim" style="font-size:11px;margin-bottom:8px">
              📳 金句卡片（适合截图）
            </div>
            <div style="display:flex;flex-direction:column;gap:6px">
              ${pkg.common.quote_cards.map(q => `
                <div style="background:var(--bg-hover);border-left:3px solid
                            var(--primary);padding:10px 14px;border-radius:0 6px 6px 0">
                  <div style="font-size:13px;color:var(--text-main)">
                    《${q.dialogue}》
                  </div>
                  <div class="text-dim" style="font-size:11px;margin-top:4px">
                    ——${q.character} · ${q.emotion}
                  </div>
                </div>
              `).join("")}
            </div>` : ""}

          <!-- 通用标签 -->
          ${pkg.common.universal_tags?.length ? `
            <div style="margin-top:12px">
              <div class="text-dim" style="font-size:11px;margin-bottom:6px">
                通用话题标签
              </div>
              <div style="display:flex;flex-wrap:wrap;gap:6px">
                ${pkg.common.universal_tags.map(t => `
                  <span style="background:var(--primary-dim);color:var(--primary);
                               padding:3px 10px;border-radius:20px;font-size:12px">
                    ${t}
                  </span>
                `).join("")}
              </div>
            </div>` : ""}
        </div>` : ""}

      <!-- 各平台素材 -->
      ${Object.entries(pkg.platforms || {}).map(([platform, copy]) => `
        <div class="card">
          <div style="display:flex;justify-content:space-between;
                      align-items:center;margin-bottom:14px">
            <div class="bold">
              ${PLATFORM_ICONS[platform]||"📫"} ${platform}
            </div>
            <button class="btn btn-ghost"
              style="font-size:11px;padding:4px 10px"
              onclick="copyPlatformCopy('${platform}',
                \`${escStr(copy.title||'')}\\n\\n${escStr(copy.body||'')}\\n\\n${escStr((copy.hashtags||[]).join(' '))}\`)">
              📵 复制文案
            </button>
          </div>

          ${copy.title ? `
            <div style="margin-bottom:10px">
              <div class="text-dim" style="font-size:11px;margin-bottom:4px">
                标题
                <span style="color:var(--text-dim)">
                  (${copy.char_count?.title||0}字)
                </span>
              </div>
              <div style="background:var(--bg-hover);border-radius:6px;
                          padding:10px;font-size:13px;font-weight:500">
                ${escHtml(copy.title)}
              </div>
            </div>` : ""}

          <div style="margin-bottom:10px">
            <div class="text-dim" style="font-size:11px;margin-bottom:4px">
              正文
              <span style="color:var(--text-dim)">
                (${copy.char_count?.body||0}字)
              </span>
            </div>
            <div style="background:var(--bg-hover);border-radius:6px;
                        padding:10px;font-size:13px;color:var(--text-sub);
                        line-height:1.8;white-space:pre-wrap">
${escHtml(copy.body||"")}
            </div>
          </div>

          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px">
            ${(copy.hashtags||[]).map(h => `
              <span style="background:rgba(124,92,252,0.15);
                           color:var(--primary);padding:3px 10px;
                           border-radius:20px;font-size:12px">
                ${h}
              </span>
            `).join("")}
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;
                      gap:8px;font-size:12px">
            <div style="background:var(--bg-hover);border-radius:6px;padding:8px">
              <div class="text-dim" style="margin-bottom:3px">置顶评论</div>
              <div style="color:var(--text-sub)">${escHtml(copy.pinned_comment||"—")}</div>
            </div>
            <div style="background:var(--bg-hover);border-radius:6px;padding:8px">
              <div class="text-dim" style="margin-bottom:3px">最佳发布时间</div>
              <div style="color:var(--success)">${copy.best_post_time||"—"}</div>
            </div>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}