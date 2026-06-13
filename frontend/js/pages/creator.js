// ═══════════════════════════════════════════════
//  角色卡工坊
// ═══════════════════════════════════════════════
function renderCreator() {
  document.getElementById("mainContent").innerHTML = `
    <div class="creator-layout" style="height:calc(100vh - 56px - 48px)">

      <!-- 左：对话区 -->
      <div class="chat-panel">
        <div class="chat-messages" id="chatMessages"></div>
        <div class="chat-input-area">
          <textarea class="chat-textarea" id="chatInput"
            placeholder="随便说，哪怕一个词…"
            onkeydown="creatorKey(event)"></textarea>
          <button class="btn btn-primary" onclick="creatorSend()">发送</button>
        </div>
      </div>

      <!-- 右：信息面板 -->
      <div class="creator-side">

        <div class="card">
          <div class="card-title">📋 收集进度</div>
          <div class="progress-list" id="progressList">
            ${["外貌","性格","世界观","画风","声线","风格矩阵"].map(k=>`
              <div class="progress-row">
                <div class="progress-lbl">
                  <span>${k}</span><span>0%</span>
                </div>
                <div class="progress-track">
                  <div class="progress-fill" style="width:0%"></div>
                </div>
              </div>
            `).join("")}
          </div>
        </div>

        <div class="card hidden" id="actionCard">
          <div class="card-title">⚡ 操作</div>
          <div class="action-group">
            <button class="btn-confirm-lg" onclick="creatorConfirm()">
              ✅ 确认角色卡
            </button>
            <button class="btn-modify-sm" onclick="creatorModify()">
              ✏️ 修改某个字段
            </button>
            <button class="btn-modify-sm" onclick="creatorRegenerate()">
              🔄 重新生成
            </button>
          </div>
        </div>

        <div class="card">
          <div class="card-title">🖼️ 角色预览图</div>
          <div class="preview-grid" id="previewGrid">
            <div class="preview-cell">等待生成</div>
            <div class="preview-cell">等待生成</div>
            <div class="preview-cell">等待生成</div>
          </div>
        </div>

        <div class="card hidden" id="voiceCard">
          <div class="card-title">🔊 声线试听</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <button class="btn btn-ghost" onclick="playVoice()"
              style="font-size:12px;padding:6px 10px">▶ 播放</button>
            <button class="btn btn-ghost" onclick="regenVoice()"
              style="font-size:12px;padding:6px 10px">🔄 重生成</button>
            <button class="btn-confirm-lg" onclick="confirmVoice()"
              style="font-size:12px;padding:6px 10px">✅ 确认</button>
          </div>
          <audio id="voiceAudio" style="display:none"></audio>
        </div>

      </div>
    </div>
  `;

  initCreatorWs();
}

function initCreatorWs() {
  if (State.creatorWs) {
    State.creatorWs.close();
  }
  State.creatorWs = new WebSocket(`ws://${location.host}/ws/creator`);

  State.creatorWs.onmessage = (e) => {
    const data = JSON.parse(e.data);
    handleCreatorMsg(data);
  };
  State.creatorWs.onerror = () => {
    showToast("WebSocket连接失败，请刷新重试", "error");
  };
}

function handleCreatorMsg(data) {
  switch(data.type) {
    case "ai_message":
      appendMsg("ai", data.content, data.state);
      updateProgress(data.progress);
      break;
    case "preview_ready":
      appendMsg("ai", data.content, data.state);
      updateProgress(data.progress);
      document.getElementById("actionCard").classList.remove("hidden");
      genPreviewImages(data.draft);
      break;
    case "card_saved":
      appendMsg("ai", data.message, data.state);
      document.getElementById("actionCard").classList.add("hidden");
      document.getElementById("voiceCard").classList.remove("hidden");
      showToast(`✅ IP已保存：${data.ip_id}`, "success");
      // 更新侧边栏计数
      fetch("/api/ip-count").then(r=>r.json()).then(d=>{
        document.getElementById("navIpCount").textContent = d.count;
      });
      break;
  }
}

function appendMsg(role, content, state) {
  const box = document.getElementById("chatMessages");
  if (!box) return;
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  if (role === "ai" && state) {
    div.innerHTML = `<span class="state-tag">${state}</span><br>${escHtml(content)}`;
  } else {
    div.textContent = content;
  }
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function updateProgress(progress) {
  if (!progress) return;
  const list = document.getElementById("progressList");
  if (!list) return;
  list.innerHTML = Object.entries(progress).map(([k,v]) => `
    <div class="progress-row">
      <div class="progress-lbl">
        <span>${k}</span><span>${v}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width:${v}%"></div>
      </div>
    </div>
  `).join("");
}

async function genPreviewImages(draft) {
  const grid = document.getElementById("previewGrid");
  if (!grid) return;
  grid.innerHTML = `
    <div class="preview-cell flex-center">
      <div class="spinner"></div>
    </div>`.repeat(3);
  try {
    const res  = await fetch("/api/generate-preview", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({draft})
    });
    const data = await res.json();
    grid.innerHTML = data.images.map((url, i) => url
      ? `<div class="preview-cell" onclick="selectPreview(${i})" id="prev_${i}">
           <img src="${url}" alt="预览${i+1}">
         </div>`
      : `<div class="preview-cell text-dim">失败</div>`
    ).join("");
  } catch(e) {
    grid.innerHTML = `<div class="preview-cell text-dim" style="grid-column:1/-1">
      生成失败，请重试</div>`;
  }
}

function selectPreview(i) {
  document.querySelectorAll(".preview-cell").forEach(c=>c.classList.remove("selected"));
  document.getElementById(`prev_${i}`)?.classList.add("selected");
}

function creatorSend() {
  const inp = document.getElementById("chatInput");
  const txt = inp.value.trim();
  if (!txt || !State.creatorWs) return;
  appendMsg("user", txt);
  State.creatorWs.send(JSON.stringify({message: txt}));
  inp.value = "";
}

function creatorKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    creatorSend();
  }
}

function creatorConfirm()    { State.creatorWs?.send(JSON.stringify({action:"confirm_card"})); }
function creatorModify()     {
  appendMsg("user", "我想修改某个字段");
  State.creatorWs?.send(JSON.stringify({message:"我想修改某个字段"}));
  document.getElementById("actionCard").classList.add("hidden");
}
function creatorRegenerate() { State.creatorWs?.send(JSON.stringify({action:"regenerate"})); }
function playVoice()         { document.getElementById("voiceAudio")?.play(); }
function regenVoice()        { State.creatorWs?.send(JSON.stringify({action:"regenerate_voice"})); }
function confirmVoice() {
  State.creatorWs?.send(JSON.stringify({action:"confirm_voice"}));
  document.getElementById("voiceCard").classList.add("hidden");
  appendMsg("ai", "✅ 声线已确认！角色卡完整创建成功。\n\n你可以前往生产中心开始制作第一集。");
  showToast("角色卡创建完成！", "success");
}