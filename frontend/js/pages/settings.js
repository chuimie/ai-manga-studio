function renderSettings() {
  document.getElementById("mainContent").innerHTML = `

    <div class="settings-section">
      <div class="settings-title">🔑 API配置</div>
      <div class="settings-row">
        <div class="settings-label">Agnes API Key</div>
        <div class="input-with-eye">
          <input class="form-input" type="password" id="agnesKey"
            placeholder="sk-...（修改后重启服务生效）">
          <button class="eye-btn" onclick="togglePwd('agnesKey')">👁</button>
        </div>
      </div>
      <div class="settings-row">
        <div class="settings-label">Agnes Base URL</div>
        <input class="form-input" type="text" id="agnesUrl"
          value="https://api.agnes.ai/v1">
      </div>
      <div class="settings-row">
        <div class="settings-label">MiMo API Key</div>
        <div class="input-with-eye">
          <input class="form-input" type="password" id="mimoKey"
            placeholder="mimo-...">
          <button class="eye-btn" onclick="togglePwd('mimoKey')">👁</button>
        </div>
      </div>
      <div style="margin-top:12px">
        <button class="btn btn-primary" onclick="showToast('配置保存至.env，请重启服务','info')">
          保存配置
        </button>
      </div>
    </div>

    <div class="settings-section">
      <div class="settings-title">🎬 生产参数</div>
      <div class="settings-row">
        <div class="settings-label">质检通过阈值</div>
        <input class="form-input" type="number" value="0.80" min="0" max="1" step="0.05"
          style="width:120px">
      </div>
      <div class="settings-row">
        <div class="settings-label">最大重试次数</div>
        <input class="form-input" type="number" value="3" min="1" max="5"
          style="width:120px">
      </div>
      <div class="settings-row">
        <div class="settings-label">图像分辨率</div>
        <select class="form-select" style="width:180px">
          <option>768 × 1024（推荐）</option>
          <option>512 × 768（省成本）</option>
          <option>1024 × 1366（高质量）</option>
        </select>
      </div>
    </div>

    <div class="settings-section">
      <div class="settings-title">💰 成本追踪</div>
      <table class="cost-table">
        <thead>
          <tr>
            <th>引擎</th><th>模型</th><th>单价</th><th>本月用量</th><th>本月费用</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>剧本</td>
            <td class="text-sub">agnes-2.0-flash</td>
            <td class="text-sub">$0.15/M token</td>
            <td class="text-sub">—</td>
            <td class="text-success">—</td>
          </tr>
          <tr>
            <td>图像</td>
            <td class="text-sub">agnes-image-2.1-flash</td>
            <td class="text-sub">$3.00/千张</td>
            <td class="text-sub">—</td>
            <td class="text-success">—</td>
          </tr>
          <tr>
            <td>视频</td>
            <td class="text-sub">agnes-video-v2.0</td>
            <td class="text-sub">$0.30/分钟</td>
            <td class="text-sub">—</td>
            <td class="text-success">—</td>
          </tr>
          <tr>
            <td>配音</td>
            <td class="text-sub">mimo-v2.5-tts</td>
            <td class="text-sub">按字符</td>
            <td class="text-sub">—</td>
            <td class="text-success">—</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="settings-section">
      <div class="settings-title">🗂️ 数据管理</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn btn-ghost" onclick="showToast('功能开发中','info')">
          📦 导出所有角色卡
        </button>
        <button class="btn btn-ghost" onclick="showToast('功能开发中','info')">
          📊 导出质检报告
        </button>
        <button class="btn btn-danger"
          onclick="confirm('确认清空所有QC报告？')&&showToast('已清空','success')">
          🗑️ 清空质检报告
        </button>
      </div>
    </div>
  `;
}

function togglePwd(id) {
  const el = document.getElementById(id);
  if (el) el.type = el.type === "password" ? "text" : "password";
}