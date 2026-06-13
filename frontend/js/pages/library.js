function renderLibrary() {
  // 顶栏过滤
  const ipFilter = State.selectedIp || "all";
  const ipOpts   = [
    `<option value="all" ${ipFilter==="all"?"selected":""}>全部IP</option>`,
    ...State.ips.map(ip =>
      `<option value="${ip.ip_id}" ${ipFilter===ip.ip_id?"selected":""}>
         ${ip.name}
       </option>`
    )
  ].join("");

  const tb = document.getElementById("topbarActions");
  tb.innerHTML = `
    <select class="form-select" style="width:160px"
      onchange="filterLibrary(this.value)">${ipOpts}</select>
    <button class="btn btn-primary" onclick="navigate('production')">
      ⚡ 去生产
    </button>
  `;

  const eps = State.selectedIp
    ? State.episodes.filter(e => e.ip_id === State.selectedIp)
    : State.episodes;

  const c = document.getElementById("mainContent");
  if (!eps.length) {
    c.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎞️</div>
        <div style="font-size:16px;font-weight:600;margin-bottom:8px">剧集库为空</div>
        <div class="text-sub" style="margin-bottom:20px">
          前往生产中心，生成第一集
        </div>
        <button class="btn btn-primary" onclick="navigate('production')">
          ⚡ 开始生产
        </button>
      </div>`;
    return;
  }

  c.innerHTML = `
    <div class="grid-3">
      ${eps.map(ep => renderEpisodeCard(ep)).join("")}
    </div>
  `;
}

function renderEpisodeCard(ep) {
  const qcBadge = ep.qc_score != null
    ? `<span class="qc-badge ${ep.qc_passed?"qc-pass":"qc-fail"}">
         ${ep.qc_passed?"✅":"⚠️"} ${(ep.qc_score*100).toFixed(0)}分
       </span>`
    : "";

  const thumb = ep.has_video
    ? `<div class="episode-thumb" style="background:#000">
         <video src="${ep.video_url}#t=0.1" preload="metadata"
                style="width:100%;height:100%;object-fit:cover"></video>
         <div class="episode-play-btn">▶</div>
       </div>`
    : `<div class="episode-thumb"><span>🎬</span></div>`;

  return `
    <div class="episode-card"
      onclick="${ep.has_video ? `playEpisode('${ep.ep_id}','${ep.video_url}','${escStr(ep.ip_name)} 第${ep.episode_num}集')` : ""}">
      ${thumb}
      <div class="episode-info">
        <div class="episode-title">${ep.ip_name} 第${ep.episode_num}集</div>
        <div class="episode-meta">${ep.ep_id} · ${formatDate(ep.created_at)}</div>
        ${qcBadge}
      </div>
    </div>
  `;
}