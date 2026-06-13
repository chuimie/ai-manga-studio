// ═══════════════════════════════════════════════
//  工具函数
// ═══════════════════════════════════════════════

function showToast(msg, type="info") {
  const c   = document.getElementById("toastContainer");
  const el  = document.createElement("div");
  el.className = `toast ${type}`;
  const icons  = {success:"✅", error:"❌", info:"ℹ️", warning:"⚠️"};
  el.innerHTML = `<span>${icons[type]||""}</span><span>${escHtml(msg)}</span>`;
  c.appendChild(el);
  setTimeout(() => { el.style.opacity="0"; el.style.transform="translateX(40px)";
    setTimeout(()=>el.remove(), 300); }, 3000);
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function escStr(s) { return String(s).replace(/'/g,"\\'"); }

function now() {
  return new Date().toTimeString().slice(0,8);
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,"0")}`;
}

function closeModal() {
  document.getElementById("videoModal").classList.remove("show");
  document.getElementById("videoPlayer").pause();
  document.getElementById("videoPlayer").src = "";
}

// ── 表格工具函数 ──────────────────────────────────
function thStyle() {
  return "padding:8px 12px;text-align:left;font-weight:500;font-size:12px;color:var(--text-sub)";
}
function tdStyle() {
  return "padding:8px 12px;vertical-align:top";
}
function metaItem(label, value) {
  return `
    <div style="background:var(--bg-hover);border-radius:6px;padding:8px 10px">
      <div style="font-size:10px;color:var(--text-dim);margin-bottom:2px">${label}</div>
      <div style="font-size:12px;color:var(--text-sub)">${value}</div>
    </div>`;
}

function scoreColor(v) {
  if (!v || v === 0) return "var(--text-dim)";
  if (v >= 0.8) return "var(--success)";
  if (v >= 0.6) return "var(--warning)";
  return "var(--error)";
}

function copyPlatformCopy(platform, text) {
  navigator.clipboard.writeText(text)
    .then(() => showToast(`${platform} 文案已复制`, "success"))
    .catch(() => showToast("复制失败", "error"));
}

function playEpisode(epId, videoUrl, title) {
  document.getElementById("modalTitle").textContent  = title;
  document.getElementById("modalMeta").textContent   = epId;
  document.getElementById("videoPlayer").src         = videoUrl;
  document.getElementById("videoModal").classList.add("show");
}

// 轮询训练中的IP状态
let loraPollingTimer = null;

function statusClass(s) {
  return s==="running" ? "status-running"
       : s==="completed" ? "status-done"
       : s==="error" ? "status-error"
       : "status-waiting";
}