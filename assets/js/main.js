/* =======================================================================
   GW-1 商业计划书 · 交互与图表
   - 滚动揭示动画 (IntersectionObserver)
   - 数字滚动计数
   - 导航隐藏/显示、返回顶部
   - ECharts 渲染全部财务/概率/估值图表（数据来自 window.MODEL_DATA）
   ======================================================================= */
(function () {
  "use strict";

  var D = window.MODEL_DATA || null;

  // 苹果风配色
  var C = {
    blue: "#0a84ff",
    cyan: "#6ee7ff",
    sky: "#36c2ff",
    green: "#30d158",
    red: "#ff453a",
    orange: "#ff9f0a",
    grey: "#86868b",
    textDark: "#1d1d1f",
    textLight: "#f5f5f7",
    gridDark: "rgba(255,255,255,0.08)",
    gridLight: "rgba(0,0,0,0.06)"
  };

  // ---------------- 滚动揭示 ----------------
  function revealAll() {
    document.querySelectorAll(".reveal:not(.in)").forEach(function (e) { e.classList.add("in"); });
  }
  function initReveal() {
    var els = document.querySelectorAll(".reveal");
    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion || !("IntersectionObserver" in window)) {
      revealAll();
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          var el = en.target;
          // 同组元素的轻微错峰
          var siblings = Array.prototype.slice.call(el.parentNode.children);
          var idx = siblings.indexOf(el);
          setTimeout(function () { el.classList.add("in"); }, Math.min(idx, 6) * 70);
          io.unobserve(el);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    els.forEach(function (e) { io.observe(e); });
  }

  // ---------------- 数字滚动 ----------------
  function animateCount(el) {
    if (el.getAttribute("data-done") === "1") return;
    el.setAttribute("data-done", "1");
    var target = parseFloat(el.getAttribute("data-count"));
    var suffix = el.getAttribute("data-suffix") || "";
    var decimals = (String(target).split(".")[1] || "").length;
    var dur = 1400, start = null, finished = false;
    function finalize() {
      if (finished) return;
      finished = true;
      el.textContent = target.toFixed(decimals) + suffix;
    }
    function step(ts) {
      if (finished) return;
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(step);
      else finalize();
    }
    requestAnimationFrame(step);
    // 兜底：requestAnimationFrame 在不可见/打印环境会被暂停，用定时器保证终值显示
    setTimeout(finalize, dur + 300);
  }
  function initCounters() {
    var nums = document.querySelectorAll("[data-count]");
    if (!("IntersectionObserver" in window)) {
      nums.forEach(animateCount); return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { animateCount(en.target); io.unobserve(en.target); }
      });
    }, { threshold: 0.5 });
    nums.forEach(function (e) { io.observe(e); });
  }

  // ---------------- 导航行为 ----------------
  function initNav() {
    var nav = document.getElementById("nav");
    var backTop = document.querySelector(".back-top");
    var last = 0;
    window.addEventListener("scroll", function () {
      var y = window.pageYOffset;
      if (y > 600 && y > last) nav.classList.add("hidden");
      else nav.classList.remove("hidden");
      last = y;
      if (backTop) backTop.classList.toggle("show", y > 800);
    }, { passive: true });
  }

  // ---------------- ECharts 公共配置 ----------------
  function baseGrid(dark) {
    return { left: 48, right: 24, top: 30, bottom: 36, containLabel: true };
  }
  function axisStyle(dark) {
    var col = dark ? "rgba(255,255,255,0.55)" : "#86868b";
    var line = dark ? C.gridDark : C.gridLight;
    return {
      axisLine: { lineStyle: { color: line } },
      axisTick: { show: false },
      axisLabel: { color: col, fontSize: 12, fontFamily: "inherit" },
      splitLine: { lineStyle: { color: line } }
    };
  }
  function tip(dark) {
    return {
      backgroundColor: dark ? "rgba(20,24,38,0.94)" : "rgba(255,255,255,0.96)",
      borderColor: dark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.08)",
      borderWidth: 1,
      textStyle: { color: dark ? "#f5f5f7" : "#1d1d1f", fontSize: 13 },
      extraCssText: "border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,0.18);backdrop-filter:blur(10px);"
    };
  }
  var charts = [];
  function make(id) {
    var dom = document.getElementById(id);
    if (!dom || !window.echarts) return null;
    var c = echarts.init(dom, null, { renderer: "canvas" });
    charts.push(c);
    return c;
  }

  // ---------------- 各图表 ----------------
  function chartRevenue() {
    var c = make("chart-revenue"); if (!c) return;
    var m = D.market;
    c.setOption({
      grid: baseGrid(false), tooltip: { trigger: "axis", valueFormatter: function (v) { return v + " 亿"; }, backgroundColor: tip(false).backgroundColor, borderColor: tip(false).borderColor, textStyle: tip(false).textStyle, extraCssText: tip(false).extraCssText },
      legend: { data: ["基线", "激进弹性"], top: 0, right: 0, textStyle: { color: C.grey, fontSize: 12 }, icon: "roundRect" },
      xAxis: Object.assign({ type: "category", data: D.oem_base.pnl.years, boundaryGap: false }, axisStyle(false)),
      yAxis: Object.assign({ type: "value", name: "亿元", nameTextStyle: { color: C.grey } }, axisStyle(false)),
      series: [
        { name: "基线", type: "line", smooth: true, data: m.revenue_base, symbolSize: 7,
          lineStyle: { width: 3, color: C.blue }, itemStyle: { color: C.blue },
          areaStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:"rgba(10,132,255,0.28)"},{offset:1,color:"rgba(10,132,255,0.02)"}]) } },
        { name: "激进弹性", type: "line", smooth: true, data: m.revenue_aggr, symbolSize: 7,
          lineStyle: { width: 3, color: C.cyan, type: "dashed" }, itemStyle: { color: C.cyan } }
      ]
    });
  }

  function chartPnl() {
    var c = make("chart-pnl"); if (!c) return;
    var p = D.oem_base.pnl;
    c.setOption({
      grid: baseGrid(false), tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, backgroundColor: tip(false).backgroundColor, borderColor: tip(false).borderColor, textStyle: tip(false).textStyle, extraCssText: tip(false).extraCssText },
      legend: { data: ["营业收入", "净利润"], top: 0, right: 0, textStyle: { color: C.grey, fontSize: 12 }, icon: "roundRect" },
      xAxis: Object.assign({ type: "category", data: p.years }, axisStyle(false)),
      yAxis: Object.assign({ type: "value", name: "亿元", nameTextStyle: { color: C.grey } }, axisStyle(false)),
      series: [
        { name: "营业收入", type: "bar", data: p.revenue.map(r=>+r.toFixed(2)), barWidth: "34%",
          itemStyle: { borderRadius: [6,6,0,0], color: new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:C.sky},{offset:1,color:C.blue}]) } },
        { name: "净利润", type: "bar", data: p.net_income.map(r=>+r.toFixed(2)), barWidth: "34%",
          itemStyle: { borderRadius: [6,6,0,0], color: C.cyan } }
      ]
    });
  }

  function chartFcf() {
    var c = make("chart-fcf"); if (!c) return;
    var cf = D.oem_base.cashflow, yrs = D.oem_base.pnl.years;
    c.setOption({
      grid: baseGrid(false), tooltip: { trigger: "axis", backgroundColor: tip(false).backgroundColor, borderColor: tip(false).borderColor, textStyle: tip(false).textStyle, extraCssText: tip(false).extraCssText },
      legend: { data: ["自由现金流", "累计现金流"], top: 0, right: 0, textStyle: { color: C.grey, fontSize: 12 }, icon: "roundRect" },
      xAxis: Object.assign({ type: "category", data: yrs }, axisStyle(false)),
      yAxis: Object.assign({ type: "value", name: "亿元", nameTextStyle: { color: C.grey } }, axisStyle(false)),
      series: [
        { name: "自由现金流", type: "bar", data: cf.fcf.map(r=>+r.toFixed(2)), barWidth: "40%",
          itemStyle: { borderRadius: [6,6,6,6], color: function(pm){ return pm.value>=0?C.blue:C.red; } } },
        { name: "累计现金流", type: "line", smooth: true, data: cf.cum_fcf.map(r=>+r.toFixed(2)), symbolSize: 7,
          lineStyle: { width: 3, color: C.orange }, itemStyle: { color: C.orange },
          markLine: { silent: true, symbol: "none", lineStyle: { color: C.grey, type: "dashed" }, data: [{ yAxis: 0 }] } }
      ]
    });
  }

  function chartCompare() {
    var c = make("chart-compare"); if (!c) return;
    var sb = D.comparison.self_built, oem = D.comparison.oem;
    var cats = ["NPV (亿)", "IRR (%)", "ROIC (%)", "Y5市值 (亿)", "CAPEX (亿)"];
    var sbData = [sb.npv, sb.irr, sb.roic, sb.valuation, sb.CAPEX];
    var oemData = [oem.npv, oem.irr, oem.roic, oem.valuation, oem.CAPEX];
    c.setOption({
      grid: baseGrid(false), tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, backgroundColor: tip(false).backgroundColor, borderColor: tip(false).borderColor, textStyle: tip(false).textStyle, extraCssText: tip(false).extraCssText },
      legend: { data: ["自建模式 (v1.0)", "OEM 模式 (重算)"], top: 0, textStyle: { color: C.grey, fontSize: 12 }, icon: "roundRect" },
      xAxis: Object.assign({ type: "category", data: cats }, axisStyle(false)),
      yAxis: Object.assign({ type: "value" }, axisStyle(false)),
      series: [
        { name: "自建模式 (v1.0)", type: "bar", data: sbData, barWidth: "30%",
          itemStyle: { borderRadius: [6,6,0,0], color: "#c7c7cc" },
          label: { show: true, position: "top", color: C.grey, fontSize: 11 } },
        { name: "OEM 模式 (重算)", type: "bar", data: oemData, barWidth: "30%",
          itemStyle: { borderRadius: [6,6,0,0], color: new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:C.sky},{offset:1,color:C.blue}]) },
          label: { show: true, position: "top", color: C.blue, fontSize: 11, fontWeight: "bold" } }
      ]
    });
  }

  function chartMc() {
    var c = make("chart-mc"); if (!c) return;
    var mc = D.montecarlo;
    var edges = mc.hist_edges, counts = mc.hist_counts;
    var cats = [], data = [];
    for (var i = 0; i < counts.length; i++) {
      var mid = (edges[i] + edges[i+1]) / 2;
      cats.push(mid.toFixed(0));
      data.push({ value: counts[i], itemStyle: { color: mid < 0 ? C.red : (mid < 12 ? C.sky : C.blue) } });
    }
    c.setOption({
      grid: baseGrid(true), tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, formatter: function(ps){ return "NPV ≈ " + ps[0].name + " 亿<br/>频数：" + ps[0].value; }, backgroundColor: tip(true).backgroundColor, borderColor: tip(true).borderColor, textStyle: tip(true).textStyle, extraCssText: tip(true).extraCssText },
      xAxis: Object.assign({ type: "category", data: cats, name: "NPV (亿元)", nameLocation: "middle", nameGap: 30, nameTextStyle: { color: C.grey } }, axisStyle(true)),
      yAxis: Object.assign({ type: "value", name: "频数", nameTextStyle: { color: C.grey } }, axisStyle(true)),
      series: [{ type: "bar", data: data, barWidth: "92%",
        markLine: { silent: true, symbol: "none", label: { color: C.cyan, fontSize: 11 },
          lineStyle: { color: C.cyan }, data: [{ xAxis: String(Math.round(mc.npv_median)), name: "中位" }] } }]
    });
  }

  function chartRisk() {
    var c = make("chart-risk"); if (!c) return;
    var rc = D.montecarlo.risk_contribution.slice(0, 7).reverse();
    var nameMap = { delay:"推广延迟", wacc:"折现率", oem_fee:"OEM加工费", rev_mult:"营业收入", cogs:"原料成本", quality_hit:"质量事故", sga:"销售费用", rd:"研发费用" };
    c.setOption({
      grid: { left: 80, right: 40, top: 16, bottom: 30, containLabel: true },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: function(v){ return v + "%"; }, backgroundColor: tip(true).backgroundColor, borderColor: tip(true).borderColor, textStyle: tip(true).textStyle, extraCssText: tip(true).extraCssText },
      xAxis: Object.assign({ type: "value", name: "解释方差 %", nameTextStyle: { color: C.grey } }, axisStyle(true)),
      yAxis: Object.assign({ type: "category", data: rc.map(function(r){ return nameMap[r.var] || r.var; }) }, axisStyle(true)),
      series: [{ type: "bar", data: rc.map(function(r){ return r.variance_pct; }), barWidth: "58%",
        itemStyle: { borderRadius: [0,6,6,0], color: new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:C.blue},{offset:1,color:C.cyan}]) },
        label: { show: true, position: "right", color: "#d1d1d6", fontSize: 11, formatter: "{c}%" } }]
    });
  }

  function chartSens() {
    var c = make("chart-sens"); if (!c) return;
    var s = D.sensitivity;
    var names = s.map(function(x){ return x.factor; });
    var swings = s.map(function(x){ return x.swing; });
    c.setOption({
      grid: { left: 130, right: 50, top: 16, bottom: 30, containLabel: true },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, formatter: function(ps){ var d=s[ps[0].dataIndex]; return d.factor+"<br/>−10%: "+d.low+" 亿<br/>+10%: "+d.high+" 亿<br/>摆动: "+d.swing+" 亿"; }, backgroundColor: tip(true).backgroundColor, borderColor: tip(true).borderColor, textStyle: tip(true).textStyle, extraCssText: tip(true).extraCssText },
      xAxis: Object.assign({ type: "value", name: "NPV 摆动 (亿元)", nameTextStyle: { color: C.grey } }, axisStyle(true)),
      yAxis: Object.assign({ type: "category", data: names.slice().reverse() }, axisStyle(true)),
      series: [{ type: "bar", data: swings.slice().reverse(), barWidth: "55%",
        itemStyle: { borderRadius: [0,6,6,0], color: new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:"#ff9f0a"},{offset:1,color:"#ffd60a"}]) },
        label: { show: true, position: "right", color: "#d1d1d6", fontSize: 11 } }]
    });
  }

  function chartFunds() {
    var c = make("chart-funds"); if (!c) return;
    var f = D.market.use_of_funds_A;
    var palette = ["#ffffff", "#cfe9ff", "#9fd4ff", "#6ebbff", "#3a98f0"];
    c.setOption({
      tooltip: { trigger: "item", formatter: "{b}<br/>{d}% · {c} 亿", backgroundColor: "rgba(255,255,255,0.96)", borderColor: "rgba(0,0,0,0.08)", textStyle: { color: "#1d1d1f" }, extraCssText: "border-radius:12px;" },
      series: [{ type: "pie", radius: ["48%", "76%"], center: ["50%", "52%"], avoidLabelOverlap: true,
        itemStyle: { borderColor: "rgba(10,90,200,0.4)", borderWidth: 2 },
        label: { color: "#fff", fontSize: 12, formatter: "{b}\n{d}%" },
        labelLine: { lineStyle: { color: "rgba(255,255,255,0.5)" } },
        data: f.map(function(x, i){ return { name: x.item, value: x.amount, itemStyle: { color: palette[i % palette.length] } }; }) }]
    });
  }

  function chartVal() {
    var c = make("chart-val"); if (!c) return;
    var v = D.oem_base.valuation;
    var cats = ["PE 法 (25×)", "PS 法 (6×)", "DCF 企业价值", "综合 (基线)", "蒙特卡洛中位", "激进弹性"];
    var vals = [v.pe, v.ps, v.dcf_ev, v.blended, D.montecarlo.val_mean, D.oem_aggr.valuation.blended];
    c.setOption({
      grid: baseGrid(true), tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: function(x){ return x + " 亿"; }, backgroundColor: tip(true).backgroundColor, borderColor: tip(true).borderColor, textStyle: tip(true).textStyle, extraCssText: tip(true).extraCssText },
      xAxis: Object.assign({ type: "category", data: cats, axisLabel: { interval: 0, rotate: 18, color: "rgba(255,255,255,0.55)", fontSize: 11 } }, axisStyle(true)),
      yAxis: Object.assign({ type: "value", name: "亿元", nameTextStyle: { color: C.grey } }, axisStyle(true)),
      series: [{ type: "bar", data: vals.map(function(x,i){ return { value: +x.toFixed(1), itemStyle: { color: i===3 ? C.cyan : (i===5 ? C.green : new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:C.sky},{offset:1,color:C.blue}])) } }; }),
        barWidth: "46%", itemStyle: { borderRadius: [6,6,0,0] },
        label: { show: true, position: "top", color: "#d1d1d6", fontSize: 11, formatter: "{c}" } }]
    });
  }

  function buildRounds() {
    var box = document.getElementById("rounds");
    if (!box || !D) return;
    D.market.funding_rounds.forEach(function (r) {
      var hot = r.round === "A 轮";
      var el = document.createElement("div");
      el.className = "round-card reveal" + (hot ? " hot" : "");
      el.innerHTML =
        '<div class="rc-round">' + r.round + '</div>' +
        '<div class="rc-amt">' + r.amount + ' 亿</div>' +
        '<div class="rc-time">' + r.time + ' · Pre ' + r.premoney + ' 亿 · 稀释 ' + r.dilution + '%</div>' +
        '<div class="rc-ms">' + r.milestone + '</div>';
      box.appendChild(el);
    });
  }

  function renderCharts() {
    if (!D || !window.echarts) {
      console.warn("MODEL_DATA 或 ECharts 未加载，图表跳过。");
      return;
    }
    chartRevenue(); chartPnl(); chartFcf(); chartCompare();
    chartMc(); chartRisk(); chartSens(); chartFunds(); chartVal();
  }

  // 仅当图表进入视口时再初始化，保证入场动画更顺滑
  var pendingCharts = null;
  function renderPendingCharts() {
    if (!pendingCharts) return;
    Object.keys(pendingCharts).forEach(function (id) {
      try { pendingCharts[id](); } catch (e) {}
    });
    pendingCharts = null;
  }
  function initChartsLazy() {
    if (!D || !window.echarts) return;
    pendingCharts = {
      "chart-revenue": chartRevenue, "chart-pnl": chartPnl, "chart-fcf": chartFcf,
      "chart-compare": chartCompare, "chart-mc": chartMc, "chart-risk": chartRisk,
      "chart-sens": chartSens, "chart-funds": chartFunds, "chart-val": chartVal
    };
    if (!("IntersectionObserver" in window)) { renderPendingCharts(); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          var id = en.target.id;
          if (pendingCharts && pendingCharts[id]) { try { pendingCharts[id](); } catch (e) {} delete pendingCharts[id]; }
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.15 });
    Object.keys(pendingCharts).forEach(function (id) {
      var dom = document.getElementById(id);
      if (dom) io.observe(dom);
    });
  }

  window.addEventListener("resize", function () {
    charts.forEach(function (c) { try { c.resize(); } catch (e) {} });
  });

  function boot() {
    initReveal();
    initCounters();
    initNav();
    buildRounds();
    initChartsLazy();
    // 兜底：若 IntersectionObserver 因后台标签/打印/不可见等原因未触发，
    // 延时后强制揭示全部内容、补跑数字与图表，保证在任何环境都完整呈现。
    setTimeout(function () {
      revealAll();
      document.querySelectorAll("[data-count]").forEach(animateCount);
      renderPendingCharts();
      charts.forEach(function (c) { try { c.resize(); } catch (e) {} });
    }, 1600);
  }
  // 兼容脚本在 DOMContentLoaded 之后才执行的情况（如外部 CDN 阻塞后）
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
