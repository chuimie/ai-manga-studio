async function renderCopyright() {
  const [recordsRes] = await Promise.all([
    fetch("/api/copyright/records").then(r => r.json())
  ]);
  const records = recordsRes.records || [];

  const tb = document.getElementById("topbarActions");
  tb.innerHTML = ``;

  document.getElementById("mainContent").innerHTML = `
    <!-- 说明 -->
    <div class="card mb-16" style="border-color:var(--warning);
         background:rgba(240,165,0,0.05)">
      <div style="display:flex;gap:14px;align-items:flex-start">
        <div style="font-size:28px">📐</div>
        <div>
          <div class="bold" style="margin-bottom:6px">版权存证说明</div>
          <div class="text-sub" style="font-size:13px;line-height:1.8">
            存证文件包含：角色设计说明、AI工具使用声明、创作过程证明、
            内容指纹（SHA-256）、Prompt调用记录摘要。<br>
            <span style="color:var(--warning)">
              ⚠️ 存证文件仅作辅助证明材料，正式版权保护建议向官方机构申请作品登记。
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- IP卡片 -->
    <div class="grid-3 mb-16">
      ${State.ips.map(ip => `
        <div class="card">
          <div style="display:flex;gap:10px;align-items:center;margin-bottom:14px">
            <div style="font-size:24px">🎁</div>
            <div>
              <div class="bold">${ip.name}</div>
              <div class="text-dim" style="font-size:11px">${ip.ip_id}</div>
            </div>
          </div>

          <div style="display:flex;flex-direction:column;gap:6px">
            <button class="btn btn-primary" style="font-size:12px"
              onclick="generateCopyright('${ip.ip_id}')">
              📫 生成存证包
            </button>
            <button class="btn btn-ghost" style="font-size:12px"
              onclick="previewCopyright('${ip.ip_id}')">
              👗 预览存证数据
            </button>
          </div>
        </div>
      `).join("")}
    </div>

    <!-- 已生成文件 -->
    ${records.length ? `
      <div class="section-header mb-16">
        <div class="section-title">📧 已生成存证文件</div>
      </div>
      <div class="card">
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead>
            <tr style="background:var(--bg-hover)">
              <th style="${thStyle()}">文件名</th>
              <th style="${thStyle()}">大小</th>
              <th style="${thStyle()}">生成时间</th>
              <th style="${thStyle()}">操作</th>
            </tr>
          </thead>
          <tbody>
            ${records.map(r => `
              <tr style="border-bottom:1px solid var(--border)">
                <td style="${tdStyle()};font-family:monospace;font-size:12px">
                  ${r.filename}
                </td>
                <td style="${tdStyle()};color:var(--text-sub)">
                  ${r.size_mb} MB
                </td>
                <td style="${tdStyle()};color:var(--text-dim)">
                  ${r.created?.slice(0,19)||""}
                </td>
                <td style="${tdStyle()}">
                  <a href="/api/copyright/download/${r.filename}"
                     download="${r.filename}">
                    <button class="btn btn-ghost" style="font-size:11px;
                      padding:4px 10px">⬇️ 下载</button>
                  </a>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>` : ""
    }
  `;
}

async function generateCopyright(ipId) {
  showToast("存证包生成中，请稍候...", "info");
}

async function previewCopyright(ipId) {
  const res    = await fetch(`/api/copyright/preview/${ipId}`).then(r=>r.json());
  const ip     = State.ips.find(i => i.ip_id === ipId);

  document.getElementById("modalTitle").textContent = `存证预览 · ${ip?.name}`;
  document.getElementById("videoPlayer").style.display = "none";

  document.getElementById("modalInfo").innerHTML = `
    <div style="padding:4px 0;font-size:13px">
      ${[
        ["存证编号",    res.record_id],
        ["内容指纹",    `<code style="font-size:10px;color:var(--primary)">${res.fingerprint?.slice(0,32)}...</code>`],
        ["已完成集数",  res.work_info?.episode_count + " 集"],
        ["总时长",      (res.work_info?.total_duration||0).toFixed(0) + " 秒"],
        ["Prompt记录数",res.creation_evidence?.prompt_call_count + " 条"],
        ["质检审核次数",res.creation_evidence?.qc_review_count + " 次"],
        ["LoRA训练",    res.creation_evidence?.lora_training ? "✅ 已完成" : "未训练"],
        ["文本模型",    res.tools_declaration?.text_model],
        ["图像模型",    res.tools_declaration?.image_model],
        ["视频模型",    res.tools_declaration?.video_model],
      ].map(([k,v]) => `
        <div style="display:flex;gap:12px;padding:8px 0;
                    border-bottom:1px solid var(--border)">
          <div style="min-width:100px;color:var(--text-dim)">${k}</div>
          <div style="color:var(--text-sub)">${v||"—"}</div>
        </div>
      `).join("")}
    </div>
  `;
  document.getElementById("videoModal").classList.add("show");
}