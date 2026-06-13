// ═══════════════════════════════════════════════
//  全局状态
// ═══════════════════════════════════════════════
const State = {
  currentPage: "dashboard",
  ips: [],
  episodes: [],
  stats: {},
  qcReports: [],
  productionCount: 1,
  productionWs: null,
  creatorWs: null,
  selectedIp: null
};

// ═══════════════════════════════════════════════
//  路由
// ═══════════════════════════════════════════════
const PAGES = {
  dashboard:  { title: "仪表盘",    sub: "系统概览",       render: renderDashboard  },
  "ip-manager":{ title: "IP管理",  sub: "管理所有角色IP", render: renderIpManager  },
  creator:    { title: "角色卡工坊",sub: "通过对话创建IP", render: renderCreator    },
  production: { title: "生产中心",  sub: "触发并监控生产", render: renderProduction },
  library:    { title: "剧集库",    sub: "浏览所有剧集",   render: renderLibrary    },
  "qc-reports":{ title: "质检报告",sub: "查看评分历史",   render: renderQcReports  },
  settings:   { title: "系统设置",  sub: "配置参数",       render: renderSettings   },
  audit:      { title:"Prompt审计", sub:"查看每次生产的完整提示词", render: renderAudit },
  lora:      { title:"LoRA训练管理", sub:"角色视觉一致性训练", render: renderLora      },
  scheduler: { title:"自动调度器",   sub:"每日生产定时任务",   render: renderScheduler },
  ipvalue:   { title: "IP价值判断", sub:   "三层过滤 · 立项决策", render: renderIpValue },
  copyright:    { title:"版权备案",   sub:"创作存证文件管理",   render: renderCopyright   },
  compare:      { title:"IP对比分析", sub:"横向数据对比",       render: renderCompare     },
  distribution: { title:"内容分发",   sub:"多平台发布素材生成", render: renderDistribution},
  evolution: { title: "AI剧情进化", sub:   "风格权重自适应优化", render: renderEvolution }
};

async function navigate(page) {
  State.currentPage = page;
  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
  document.querySelector(`.nav-item[onclick="navigate('${page}')"]`)
          ?.classList.add("active");
  document.getElementById("pageTitle").textContent    = PAGES[page].title;
  document.getElementById("pageSubtitle").textContent = PAGES[page].sub;
  document.getElementById("topbarActions").innerHTML  = "";
  document.getElementById("mainContent").innerHTML    =
    `<div class="flex-center" style="height:200px"><div class="spinner"></div></div>`;
  await loadData(page);
  PAGES[page].render();
}

async function loadData(page) {
  try {
    if (["dashboard","ip-manager","creator","production","library"].includes(page)) {
      const res = await fetch("/api/ips");
      const d   = await res.json();
      State.ips = d.ips || [];
      document.getElementById("navIpCount").textContent = State.ips.length;
    }
    if (["dashboard","library"].includes(page)) {
      const res     = await fetch("/api/episodes");
      State.episodes = (await res.json()).episodes || [];
    }
    if (page === "dashboard") {
      const res   = await fetch("/api/stats");
      State.stats = await res.json();
      const cost  = State.stats.total_cost_usd || 0;
      document.getElementById("sidebarCost").textContent    = "$" + cost.toFixed(2);
      document.getElementById("sidebarCostCny").textContent = (cost * 7.2).toFixed(2);
    }
    if (page === "qc-reports") {
      const res       = await fetch("/api/qc");
      State.qcReports = (await res.json()).reports || [];
    }
  } catch(e) {
    console.error("数据加载失败:", e);
  }
}

function filterLibrary(ipId) {
  State.selectedIp = ipId === "all" ? null : ipId;
  renderLibrary();
}

function adjustCount(delta) {
  State.productionCount = Math.max(1, Math.min(10, State.productionCount + delta));
  document.getElementById("countDisplay").textContent = State.productionCount;
  updateEstCost();
}

function updateEstCost() {
  const cost = (State.productionCount * 1.53).toFixed(2);
  const el   = document.getElementById("estCost");
  if (el) el.textContent = cost;
}