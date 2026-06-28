from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.bike_template_engine import (  # noqa: E402
    MODE_META,
    PART_FROM_API,
    build_bike_catalog,
    build_render_state,
    build_template_matrix,
    load_template_packages,
    map_generic_dataset,
    write_template_package_artifacts,
)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _bike_options_by_template(bikes: list[dict]) -> dict[str, dict]:
    examples: dict[str, dict] = {}
    for bike in bikes:
        template_type = bike["templateType"]
        if template_type not in examples:
            examples[template_type] = bike
    return examples


def _build_engine_page(engine_data: dict) -> str:
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>bike-template-engine</title>
  <style>
    :root {
      --bg: #f4f5f7;
      --card: rgba(255,255,255,0.88);
      --line: #d8dde6;
      --text: #1f2937;
      --muted: #6b7280;
      --accent: #2f6fe4;
      --success: #2c8a5a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: linear-gradient(180deg, #eef2f8 0%, #f7f8fb 100%);
      color: var(--text);
    }
    .shell {
      width: min(1460px, calc(100vw - 32px));
      margin: 24px auto 48px;
      display: grid;
      gap: 16px;
    }
    .hero, .card {
      background: var(--card);
      border: 1px solid rgba(255,255,255,0.72);
      border-radius: 24px;
      box-shadow: 0 20px 60px rgba(15, 23, 42, 0.08);
      backdrop-filter: blur(18px);
    }
    .hero {
      padding: 24px 28px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 20px;
    }
    .hero h1 {
      margin: 0 0 8px;
      font-size: 30px;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      max-width: 780px;
      line-height: 1.6;
    }
    .hero-links {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .hero-links a, .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 10px 14px;
      border-radius: 999px;
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
    }
    .layout {
      display: grid;
      grid-template-columns: 320px 1fr 340px;
      gap: 16px;
    }
    .panel {
      padding: 20px;
      min-height: 200px;
    }
    .panel h2 {
      margin: 0 0 14px;
      font-size: 18px;
    }
    .small {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }
    select, input[type="search"] {
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: #fff;
      font: inherit;
    }
    input[type="search"]::placeholder { color: #9aa4b2; }
    .control-stack {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }
    .inline-actions {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }
    .mode-group {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 14px;
    }
    .mode-btn, .part-btn {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      cursor: pointer;
      transition: all .2s ease;
    }
    .mode-btn {
      padding: 10px 14px;
      border-radius: 999px;
      font: inherit;
      font-size: 13px;
      font-weight: 600;
    }
    .mode-btn.active {
      color: #fff;
      background: var(--accent);
      border-color: transparent;
      box-shadow: 0 10px 24px rgba(47, 111, 228, 0.25);
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 16px;
    }
    .stat {
      padding: 14px;
      border-radius: 18px;
      background: rgba(15, 23, 42, 0.03);
      border: 1px solid rgba(15, 23, 42, 0.04);
    }
    .stat b {
      display: block;
      font-size: 22px;
      margin-top: 4px;
    }
    .stage-wrap {
      padding: 20px;
    }
    .stage-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 16px;
    }
    .stage-top h2 {
      margin: 0;
      font-size: 22px;
    }
    .stage {
      min-height: 520px;
      border-radius: 24px;
      background: radial-gradient(circle at top right, rgba(47,111,228,0.07), transparent 36%), #fbfbfc;
      border: 1px solid rgba(15, 23, 42, 0.06);
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      padding: 20px;
    }
    .stage svg {
      width: 100%;
      max-width: 860px;
      height: auto;
      overflow: visible;
    }
    .stage [data-part-key] {
      cursor: pointer;
      pointer-events: all;
      transform-box: fill-box;
      transform-origin: center center;
      will-change: transform, filter, opacity;
      transition:
        opacity .18s ease,
        transform .24s cubic-bezier(.22,.8,.22,1),
        filter .24s cubic-bezier(.22,.8,.22,1),
        stroke .2s ease,
        stroke-width .2s ease;
    }
    .stage [data-part-key][data-render-status="template_only"] {
      opacity: .42;
    }
    .stage [data-part-key][data-dimmed="true"] {
      opacity: .22 !important;
      filter: saturate(.65);
    }
    .stage [data-part-key][data-hovered="true"] {
      transform: translateY(-4px) scale(1.045);
      filter: drop-shadow(0 10px 18px rgba(15, 23, 42, 0.18));
    }
    .stage [data-part-key][data-selected="true"] {
      transform: translateY(-8px) scale(1.11);
      filter:
        drop-shadow(0 16px 28px rgba(15, 23, 42, 0.22))
        drop-shadow(0 0 0 rgba(47, 111, 228, 0.28));
    }
    .legend {
      display: flex;
      flex-direction: column;
      gap: 8px;
      min-width: 220px;
    }
    .legend-bar {
      height: 14px;
      border-radius: 999px;
      border: 1px solid rgba(15,23,42,0.06);
    }
    .legend-labels {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: var(--muted);
    }
    .parts {
      display: grid;
      gap: 10px;
      max-height: 680px;
      overflow: auto;
      padding-right: 6px;
    }
    .part-btn {
      width: 100%;
      text-align: left;
      padding: 14px;
      border-radius: 18px;
    }
    .part-btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
    }
    .part-btn.active {
      border-color: transparent;
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.12);
    }
    .part-meta {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
    }
    .detail {
      display: grid;
      gap: 12px;
      min-height: 164px;
    }
    .subtools {
      display: grid;
      gap: 10px;
      margin-top: 12px;
      margin-bottom: 12px;
    }
    .detail-card {
      padding: 16px;
      border-radius: 20px;
      background: rgba(15, 23, 42, 0.03);
      border: 1px solid rgba(15, 23, 42, 0.05);
      animation: detailCardIn .28s cubic-bezier(.22,.8,.22,1);
    }
    .detail-card h3 {
      margin: 0 0 8px;
      font-size: 18px;
    }
    .detail-card p {
      margin: 0;
      font-size: 13px;
      color: var(--muted);
      line-height: 1.6;
    }
    .kv {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
      font-size: 13px;
    }
    .kv div {
      padding: 12px;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 16px;
    }
    .matrix {
      display: grid;
      gap: 8px;
      margin-top: 12px;
      max-height: 300px;
      overflow: auto;
    }
    .matrix-row {
      display: grid;
      grid-template-columns: 120px repeat(6, minmax(0, 1fr));
      gap: 6px;
      align-items: center;
      font-size: 12px;
    }
    .matrix-cell {
      padding: 8px 6px;
      border-radius: 12px;
      text-align: center;
      border: 1px solid rgba(15, 23, 42, 0.04);
      color: #fff;
      min-height: 38px;
    }
    .hint {
      margin-top: 10px;
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(47, 111, 228, 0.08);
      color: #2646a5;
      font-size: 12px;
      line-height: 1.5;
    }
    .stage-status {
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
    }
    .empty-state {
      padding: 22px;
      border-radius: 18px;
      background: rgba(15, 23, 42, 0.035);
      border: 1px dashed rgba(15, 23, 42, 0.12);
      color: var(--muted);
      text-align: center;
      line-height: 1.7;
    }
    @keyframes detailCardIn {
      0% {
        opacity: 0;
        transform: translateY(10px) scale(.985);
      }
      100% {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
    }
    @media (max-width: 1180px) {
      .layout { grid-template-columns: 1fr; }
      .matrix-row { grid-template-columns: 100px repeat(4, minmax(0, 1fr)); }
      .inline-actions { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div>
        <div class="chip">Phase 1 · bike-template-engine</div>
        <h1>自行车模板热力图引擎</h1>
        <p>该页面由标准模板包、标准 bike payload 和引擎运行时共同驱动，支持模板热力图、图例切换、部件详情、模板覆盖率和品牌矩阵。它是当前项目从展示页走向可复用工具的运行时核心。</p>
      </div>
      <div class="hero-links">
        <a href="./template_studio.html">打开 Template Studio</a>
        <a href="./dataset_mapper.html">打开 Dataset Mapper</a>
      </div>
    </section>
    <section class="layout">
      <div class="card panel">
        <h2>控制台</h2>
        <div class="small">选择车型、切换模式，查看当前模板与数据的绑定状态。</div>
        <div class="control-stack">
          <select id="bikeSelect"></select>
          <input id="bikeSearch" type="search" placeholder="搜索品牌 / 车型 / 类型" />
          <select id="templateFilter">
            <option value="all">全部模板</option>
            <option value="road">仅公路模板</option>
            <option value="mountain">仅山地模板</option>
          </select>
          <div class="inline-actions">
            <button class="mode-btn" id="prevBikeBtn" type="button">上一辆</button>
            <button class="mode-btn" id="nextBikeBtn" type="button">下一辆</button>
            <button class="mode-btn" id="clearFiltersBtn" type="button">清空筛选</button>
          </div>
        </div>
        <div class="mode-group" id="modeGroup"></div>
        <div class="stats" id="stats"></div>
        <div class="hint" id="controlHint">支持搜索车型、按模板过滤，并可点击中间 SVG 部件直接联动右侧详情。</div>
      </div>
      <div class="card stage-wrap">
        <div class="stage-top">
          <div>
            <h2 id="stageTitle">模板舞台</h2>
            <div class="small" id="stageSubtitle"></div>
            <div class="stage-status" id="stageStatus"></div>
          </div>
          <div class="legend">
            <div id="legendTitle" class="small"></div>
            <div id="legendBar" class="legend-bar"></div>
            <div class="legend-labels"><span>低</span><span>中</span><span>高</span></div>
          </div>
        </div>
        <div class="stage" id="stage"></div>
      </div>
      <div class="card panel">
        <h2>部件详情</h2>
        <div class="detail" id="detailPanel"></div>
        <h2 style="margin-top:18px;">部件列表</h2>
        <div class="subtools">
          <input id="partSearch" type="search" placeholder="搜索部件名 / 组件名 / 状态" />
        </div>
        <div class="parts" id="partsList"></div>
      </div>
    </section>
    <section class="card panel">
      <h2>品牌-部件矩阵预览</h2>
      <div class="small">这是 engine runtime 聚合出的一个简化矩阵，用于验证同一协议可以同时驱动单车热力图与全库概览视图。</div>
      <div class="matrix" id="matrix"></div>
    </section>
  </div>
  <script>
    window.__ENGINE_DATA__ = __ENGINE_DATA_PAYLOAD__;
  </script>
  <script>
    const DATA = window.__ENGINE_DATA__;
    const state = {
      bikeId: DATA.defaultBikeId,
      mode: "price_score",
      selectedPartKey: null
    };

    const bikeSelect = document.getElementById("bikeSelect");
    const bikeSearch = document.getElementById("bikeSearch");
    const templateFilter = document.getElementById("templateFilter");
    const prevBikeBtn = document.getElementById("prevBikeBtn");
    const nextBikeBtn = document.getElementById("nextBikeBtn");
    const clearFiltersBtn = document.getElementById("clearFiltersBtn");
    const modeGroup = document.getElementById("modeGroup");
    const stats = document.getElementById("stats");
    const stage = document.getElementById("stage");
    const partsList = document.getElementById("partsList");
    const detailPanel = document.getElementById("detailPanel");
    const stageTitle = document.getElementById("stageTitle");
    const stageSubtitle = document.getElementById("stageSubtitle");
    const stageStatus = document.getElementById("stageStatus");
    const legendTitle = document.getElementById("legendTitle");
    const legendBar = document.getElementById("legendBar");
    const matrix = document.getElementById("matrix");
    const partSearch = document.getElementById("partSearch");

    const MODE_GRADIENTS = {
      price_score: "linear-gradient(90deg, #fff6ef 0%, #f7b37a 50%, #991f17 100%)",
      quality_score: "linear-gradient(90deg, #eef6ff 0%, #8eb7ff 50%, #15308a 100%)",
      value_score: "linear-gradient(90deg, #effcf8 0%, #8be0cb 50%, #0d6b66 100%)"
    };

    state.bikeQuery = "";
    state.templateFilter = "all";
    state.partQuery = "";
    state.hoveredPartKey = null;

    function filteredBikeOptions() {
      const query = state.bikeQuery.trim().toLowerCase();
      return DATA.bikeOptions.filter((bike) => {
        const templatePass = state.templateFilter === "all" || bike.templateType === state.templateFilter;
        const queryPass = !query || `${bike.brand} ${bike.bikeName} ${bike.bikeType} ${bike.templateType}`.toLowerCase().includes(query);
        return templatePass && queryPass;
      });
    }

    function syncBikeSelection() {
      const options = filteredBikeOptions();
      if (!options.length) return options;
      if (!options.some((bike) => bike.bikeId === state.bikeId)) {
        state.bikeId = options[0].bikeId;
      }
      return options;
    }

    function currentRender() {
      return DATA.rendersByBikeId[state.bikeId]?.[state.mode] || null;
    }

    function visibleParts(renderState) {
      const query = state.partQuery.trim().toLowerCase();
      if (!renderState) return [];
      return renderState.parts.filter((part) => {
        if (!query) return true;
        return [
          part.displayName,
          part.componentName,
          part.sourceType,
          part.render.status,
          ...(part.templateLabels || [])
        ].filter(Boolean).join(" ").toLowerCase().includes(query);
      });
    }

    function applyTemplateColoring(root, renderState) {
      const partsByTemplate = new Map();
      renderState.parts.forEach((part) => {
        partsByTemplate.set(part.partKey, part);
        part.templateLabels.forEach((label) => {
          partsByTemplate.set(label, part);
        });
      });
      Object.entries(renderState.template.mapping).forEach(([mappingKey, ids]) => {
        const part = partsByTemplate.get(mappingKey);
        ids.forEach((id) => {
          const node = root.querySelector("#" + CSS.escape(id));
          if (!node) return;
          const interactiveKey = part ? part.partKey : mappingKey;
          const color = part ? part.render.fillColor : "#d8d8d8";
          node.setAttribute("data-part-key", interactiveKey);
          node.setAttribute("data-label", mappingKey);
          node.setAttribute("data-component-name", part?.componentName || "");
          node.setAttribute("data-render-status", part ? part.render.status : "template_only");
          if (node.tagName.toLowerCase() === "line") {
            node.style.stroke = color;
            node.style.opacity = part ? String(part.render.strokeOpacity) : "0.45";
          } else {
            node.style.fill = color;
            node.style.stroke = state.selectedPartKey && interactiveKey === state.selectedPartKey ? "#0f172a" : "#bcbcbc";
            node.style.strokeWidth = state.selectedPartKey && interactiveKey === state.selectedPartKey ? "2.2" : "0.969463";
            node.style.opacity = part ? String(Math.max(0.55, part.render.strokeOpacity)) : "0.45";
          }
        });
      });
    }

    function applyInteractiveState(root) {
      const hasSelection = Boolean(state.selectedPartKey);
      root.querySelectorAll("[data-part-key]").forEach((node) => {
        const partKey = node.getAttribute("data-part-key");
        node.setAttribute("data-hovered", state.hoveredPartKey && state.hoveredPartKey === partKey ? "true" : "false");
        node.setAttribute("data-selected", state.selectedPartKey && state.selectedPartKey === partKey ? "true" : "false");
        node.setAttribute(
          "data-dimmed",
          hasSelection && state.selectedPartKey !== partKey ? "true" : "false"
        );
      });
    }

    function updateStageMotionState() {
      const svg = stage.querySelector("svg");
      if (!svg) return;
      applyInteractiveState(svg);
    }

    function bindStageInteractions(root, renderState) {
      root.querySelectorAll("[data-part-key]").forEach((node) => {
        const partKey = node.getAttribute("data-part-key");
        if (!partKey) return;
        node.addEventListener("click", () => {
          state.selectedPartKey = partKey === state.selectedPartKey ? null : partKey;
          renderAll();
        });
        node.addEventListener("mouseenter", () => {
          state.hoveredPartKey = partKey;
          applyInteractiveState(root);
          const part = renderState.parts.find((item) => item.partKey === partKey);
          stageStatus.textContent = part
            ? `悬停部件：${part.displayName} · ${part.componentName || "未绑定组件"} · 当前模式值 ${part.metrics[state.mode] ?? "N/A"}`
            : `悬停部件：${partKey} · 当前模板存在该区域，但暂无部件数据。`;
        });
        node.addEventListener("mouseleave", () => {
          if (state.hoveredPartKey === partKey) {
            state.hoveredPartKey = null;
          }
          applyInteractiveState(root);
          stageStatus.textContent = "可点击中间模板上的部件区域，快速联动右侧详情卡与部件列表。";
        });
      });
    }

    function renderStage() {
      const renderState = currentRender();
      if (!renderState) {
        stage.innerHTML = '<div class="empty-state">当前筛选条件下没有可展示车型。<br/>请清空筛选或切换模板条件。</div>';
        stageTitle.textContent = "模板舞台";
        stageSubtitle.textContent = "未命中车型";
        stageStatus.textContent = "尝试清空搜索词，或切换回全部模板。";
        legendTitle.textContent = "暂无图例";
        legendBar.style.background = "linear-gradient(90deg, #eef2f7, #d8dde6)";
        return;
      }
      stage.innerHTML = renderState.template.svgBase;
      const svg = stage.querySelector("svg");
      if (svg) {
        applyTemplateColoring(svg, renderState);
        applyInteractiveState(svg);
        bindStageInteractions(svg, renderState);
      }
      stageTitle.textContent = `${renderState.bike.brand} / ${renderState.bike.bikeName}`;
      stageSubtitle.textContent = `${renderState.template.label} · ${renderState.modeMeta.label}模式 · 模板覆盖率 ${Math.round((renderState.summary.templateCoverage || 0) * 100)}%`;
      stageStatus.textContent = "可点击中间模板上的部件区域，快速联动右侧详情卡与部件列表。";
      legendTitle.textContent = renderState.modeMeta.legendTitle;
      legendBar.style.background = MODE_GRADIENTS[state.mode];
    }

    function renderStats() {
      const renderState = currentRender();
      if (!renderState) {
        stats.innerHTML = [
          ["候选车型", filteredBikeOptions().length],
          ["部件数", "0"],
          ["覆盖率", "0%"],
          ["证据强度", "0"]
        ].map(([label, value]) => `<div class="stat"><span class="small">${label}</span><b>${value}</b></div>`).join("");
        return;
      }
      const summary = renderState.summary;
      stats.innerHTML = [
        ["候选车型", filteredBikeOptions().length],
        ["部件数", summary.partsCount ?? renderState.parts.length],
        ["已映射", summary.mappedPartsCount ?? 0],
        ["覆盖率", `${Math.round((summary.templateCoverage || 0) * 100)}%`]
      ].map(([label, value]) => `<div class="stat"><span class="small">${label}</span><b>${value}</b></div>`).join("");
    }

    function renderModes() {
      modeGroup.innerHTML = Object.entries(DATA.modes).map(([modeKey, meta]) => `
        <button class="mode-btn ${state.mode === modeKey ? "active" : ""}" data-mode="${modeKey}">
          ${meta.label}
        </button>
      `).join("");
      modeGroup.querySelectorAll(".mode-btn").forEach((button) => {
        button.addEventListener("click", () => {
          state.mode = button.dataset.mode;
          state.selectedPartKey = null;
          state.hoveredPartKey = null;
          renderAll();
        });
      });
    }

    function renderBikeSelect() {
      const options = syncBikeSelection();
      bikeSelect.innerHTML = options.map((bike) => `
        <option value="${bike.bikeId}" ${bike.bikeId === state.bikeId ? "selected" : ""}>
          ${bike.brand} / ${bike.bikeName} · ${bike.bikeType} · ${bike.templateType}
        </option>
      `).join("");
      bikeSelect.disabled = !options.length;
      bikeSelect.onchange = () => {
        state.bikeId = bikeSelect.value;
        state.selectedPartKey = null;
        state.hoveredPartKey = null;
        renderAll();
      };
    }

    function renderParts() {
      const renderState = currentRender();
      const parts = visibleParts(renderState);
      if (!renderState || !parts.length) {
        partsList.innerHTML = '<div class="empty-state">当前没有命中的部件。<br/>可尝试清空右侧搜索词。</div>';
        return;
      }
      partsList.innerHTML = parts.map((part) => `
        <button class="part-btn ${state.selectedPartKey === part.partKey ? "active" : ""}" data-part="${part.partKey}" style="border-left: 6px solid ${part.render.fillColor};">
          <div><strong>${part.displayName}</strong></div>
          <div class="small">${part.componentName || "未绑定组件"}</div>
          <div class="part-meta">
            <span>${part.sourceType}</span>
            <span>${part.render.status}</span>
            <span>${part.metrics[state.mode] ?? "N/A"}</span>
          </div>
        </button>
      `).join("");
      partsList.querySelectorAll(".part-btn").forEach((button) => {
        button.addEventListener("click", () => {
          state.selectedPartKey = button.dataset.part === state.selectedPartKey ? null : button.dataset.part;
          renderAll();
        });
        button.addEventListener("mouseenter", () => {
          state.hoveredPartKey = button.dataset.part;
          updateStageMotionState();
        });
        button.addEventListener("mouseleave", () => {
          if (state.hoveredPartKey === button.dataset.part) {
            state.hoveredPartKey = null;
          }
          updateStageMotionState();
        });
      });
    }

    function renderDetail() {
      const renderState = currentRender();
      const parts = visibleParts(renderState);
      const selectedPart = state.selectedPartKey
        ? (parts.find((item) => item.partKey === state.selectedPartKey) || renderState.parts.find((item) => item.partKey === state.selectedPartKey))
        : null;
      const part = selectedPart || (!state.selectedPartKey ? parts[0] : null);
      if (!part && state.selectedPartKey) {
        detailPanel.innerHTML = `
          <div class="detail-card">
            <h3>${state.selectedPartKey}</h3>
            <p>当前点击的是模板中的已标注区域，但该车型暂未导出对应部件数据。</p>
            <div class="small">这通常意味着官网规格缺失、字段未抽取到，或当前车型只能使用模板占位而非真实部件记录。</div>
          </div>
        `;
        return;
      }
      if (!part) {
        detailPanel.innerHTML = '<div class="detail-card"><p>暂无可展示部件。</p></div>';
        return;
      }
      detailPanel.innerHTML = `
        <div class="detail-card">
          <h3>${part.displayName}</h3>
          <p>${part.componentName || "未绑定组件"}${part.brandHint ? ` · ${part.brandHint}` : ""}</p>
          <div class="kv">
            <div><b>sourceType</b><br>${part.sourceType}</div>
            <div><b>render</b><br>${part.render.status}</div>
            <div><b>offers</b><br>${part.evidence.offersCount}</div>
            <div><b>reviews</b><br>${part.evidence.reviewsCount}</div>
            <div><b>price</b><br>${part.metrics.price_score ?? "N/A"}</div>
            <div><b>quality</b><br>${part.metrics.quality_score ?? "N/A"}</div>
            <div><b>value</b><br>${part.metrics.value_score ?? "N/A"}</div>
            <div><b>labels</b><br>${part.templateLabels.join(", ") || "template-missing"}</div>
          </div>
        </div>
      `;
    }

    function renderMatrix() {
      const mode = state.mode;
      const topParts = DATA.matrix.parts.slice(0, 6);
      const rows = DATA.matrix.brands.map((brand) => {
        const cells = topParts.map((part) => {
          const cell = DATA.matrix.modes[mode][brand][part];
          const avg = cell.avg;
          const color = avg == null ? "#d9dde3" : (mode === "price_score"
            ? (avg > 200 ? "#991f17" : avg > 80 ? "#d46c3c" : "#efc3a1")
            : mode === "quality_score"
              ? (avg > 0.85 ? "#15308a" : avg > 0.7 ? "#4b77ee" : "#aac4ff")
              : (avg > 0.32 ? "#0d6b66" : avg > 0.26 ? "#24a491" : "#9fe0cf"));
          const text = avg == null ? "N/A" : `${Number(avg).toFixed(mode === "price_score" ? 0 : 2)} (${cell.count})`;
          return `<div class="matrix-cell" style="background:${color};">${text}</div>`;
        }).join("");
        return `<div class="matrix-row"><strong>${brand}</strong>${cells}</div>`;
      }).join("");
      const header = `<div class="matrix-row"><strong>brand</strong>${topParts.map((part) => `<div class="chip">${part}</div>`).join("")}</div>`;
      matrix.innerHTML = header + rows;
    }

    function renderAll() {
      renderBikeSelect();
      renderModes();
      renderStats();
      renderStage();
      renderParts();
      renderDetail();
      renderMatrix();
    }

    bikeSearch.addEventListener("input", () => {
      state.bikeQuery = bikeSearch.value;
      state.selectedPartKey = null;
      state.hoveredPartKey = null;
      renderAll();
    });
    templateFilter.addEventListener("change", () => {
      state.templateFilter = templateFilter.value;
      state.selectedPartKey = null;
      state.hoveredPartKey = null;
      renderAll();
    });
    partSearch.addEventListener("input", () => {
      state.partQuery = partSearch.value;
      renderAll();
    });
    prevBikeBtn.addEventListener("click", () => {
      const options = syncBikeSelection();
      if (!options.length) return;
      const index = Math.max(0, options.findIndex((item) => item.bikeId === state.bikeId));
      state.bikeId = options[(index - 1 + options.length) % options.length].bikeId;
      state.selectedPartKey = null;
      state.hoveredPartKey = null;
      renderAll();
    });
    nextBikeBtn.addEventListener("click", () => {
      const options = syncBikeSelection();
      if (!options.length) return;
      const index = Math.max(0, options.findIndex((item) => item.bikeId === state.bikeId));
      state.bikeId = options[(index + 1) % options.length].bikeId;
      state.selectedPartKey = null;
      state.hoveredPartKey = null;
      renderAll();
    });
    clearFiltersBtn.addEventListener("click", () => {
      state.bikeQuery = "";
      state.templateFilter = "all";
      state.partQuery = "";
      state.hoveredPartKey = null;
      bikeSearch.value = "";
      templateFilter.value = "all";
      partSearch.value = "";
      renderAll();
    });

    renderAll();
  </script>
</body>
</html>
"""
    return template.replace("__ENGINE_DATA_PAYLOAD__", json.dumps(engine_data, ensure_ascii=False))


def _build_template_studio_page(studio_data: dict) -> str:
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>template studio</title>
  <style>
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: #f4f6fa;
      color: #1f2937;
    }
    * { box-sizing: border-box; }
    .shell { width: min(1480px, calc(100vw - 32px)); margin: 24px auto; display: grid; gap: 16px; }
    .card {
      background: rgba(255,255,255,0.92);
      border-radius: 24px;
      border: 1px solid rgba(255,255,255,0.76);
      box-shadow: 0 20px 60px rgba(15,23,42,0.08);
      padding: 22px;
    }
    .hero { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; }
    h1, h2, h3 { margin: 0; }
    .muted { color:#6b7280; line-height:1.6; font-size:13px; }
    .layout { display:grid; grid-template-columns: 320px 1fr 380px; gap:16px; }
    select, textarea, button, input[type="search"] {
      width: 100%;
      font: inherit;
      border-radius: 14px;
      border: 1px solid #d8dde6;
    }
    select, button, input[type="search"] { padding: 12px 14px; background:#fff; }
    textarea {
      min-height: 280px;
      padding: 14px;
      resize: vertical;
      background: #fbfcfe;
      line-height: 1.55;
    }
    .stage {
      min-height: 620px;
      border-radius: 22px;
      border: 1px solid rgba(15,23,42,0.06);
      background: #fbfcff;
      display:flex;
      align-items:center;
      justify-content:center;
      padding: 18px;
      overflow:hidden;
    }
    .stage svg { width: 100%; max-width: 880px; height: auto; }
    .part-grid, .id-list {
      display:grid;
      gap:10px;
      margin-top: 12px;
    }
    .part-btn {
      padding: 10px 12px;
      text-align:left;
      background:#fff;
      cursor:pointer;
    }
    .part-btn.active {
      color:#fff;
      border-color:transparent;
      background:#2f6fe4;
      box-shadow: 0 12px 24px rgba(47,111,228,0.24);
    }
    .toolbar { display:flex; gap:10px; flex-wrap:wrap; margin-top: 12px; }
    .toolbar button { width:auto; cursor:pointer; }
    .toolbar input[type="search"] { max-width: 240px; }
    .tag {
      display:inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: #eff6ff;
      color: #2952c3;
      font-size: 12px;
      margin: 4px 6px 0 0;
    }
    .id-list div {
      padding: 10px 12px;
      border-radius: 12px;
      background:#fff;
      border:1px solid #e3e7ef;
      font-size: 12px;
      word-break: break-all;
    }
    .status {
      margin-top: 12px;
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(47,111,228,0.08);
      color: #2952c3;
      font-size: 12px;
      line-height: 1.6;
    }
    .id-list button {
      width: 100%;
      text-align: left;
      padding: 10px 12px;
      border-radius: 12px;
      background:#fff;
      border:1px solid #e3e7ef;
      font-size: 12px;
      word-break: break-all;
      cursor: pointer;
    }
    .id-list button:hover {
      border-color: #8ab0ff;
      box-shadow: 0 10px 18px rgba(47,111,228,0.12);
    }
    @media (max-width: 1180px) { .layout { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="shell">
    <section class="card hero">
      <div>
        <div class="tag">Phase 2 · template studio</div>
        <h1 style="margin-top:8px;">模板维护工作台</h1>
        <p class="muted">该页面用于可视化维护 SVG 标签映射。可选择 road / mountain 模板，查看当前 partKey 到 svg id 的绑定，修改映射草案并实时预览高亮效果。</p>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;">
        <a class="tag" href="./index.html">返回 Engine</a>
        <a class="tag" href="./dataset_mapper.html">打开 Mapper</a>
      </div>
    </section>
    <section class="layout">
      <div class="card">
        <h2>模板与部件</h2>
        <div class="muted" style="margin-top:8px;">选择模板并查看其支持部件。</div>
        <div style="margin-top:12px;">
          <select id="templateSelect"></select>
        </div>
        <div class="toolbar">
          <input id="partSearch" type="search" placeholder="搜索 partKey" />
        </div>
        <div class="part-grid" id="partGrid"></div>
      </div>
      <div class="card">
        <h2 id="studioTitle">模板预览</h2>
        <div class="muted" id="studioSubtitle" style="margin-top:8px;"></div>
        <div class="toolbar">
          <button id="applyMappingBtn">应用映射草案</button>
          <button id="resetMappingBtn">恢复默认映射</button>
          <button id="formatMappingBtn">格式化 JSON</button>
          <button id="downloadMappingBtn">下载 mapping.json</button>
        </div>
        <div class="status" id="studioStatus">点击左侧部件后，可直接点击中间 SVG 元素为该部件增删映射。</div>
        <div class="stage" id="studioStage" style="margin-top:14px;"></div>
      </div>
      <div class="card">
        <h2>映射草案</h2>
        <div class="muted" style="margin-top:8px;">你可以直接修改 `mapping.json` 草案并在中间舞台实时验证。</div>
        <textarea id="mappingEditor"></textarea>
        <h3 style="margin-top:16px;">当前部件绑定 IDs</h3>
        <div class="toolbar">
          <button id="copySelectedIdsBtn">复制当前部件 IDs</button>
        </div>
        <div class="id-list" id="mappedIds"></div>
        <h3 style="margin-top:16px;">未绑定 IDs</h3>
        <div class="toolbar">
          <input id="unboundFilter" type="search" placeholder="筛选未绑定 id" />
        </div>
        <div class="id-list" id="unboundIds"></div>
      </div>
    </section>
  </div>
  <script>
    window.__STUDIO_DATA__ = __STUDIO_DATA_PAYLOAD__;
  </script>
  <script>
    const DATA = window.__STUDIO_DATA__;
    const state = {
      templateType: DATA.defaultTemplateType,
      selectedPart: null,
      customMapping: null
    };
    const templateSelect = document.getElementById("templateSelect");
    const partGrid = document.getElementById("partGrid");
    const studioStage = document.getElementById("studioStage");
    const mappingEditor = document.getElementById("mappingEditor");
    const mappedIds = document.getElementById("mappedIds");
    const unboundIds = document.getElementById("unboundIds");
    const studioTitle = document.getElementById("studioTitle");
    const studioSubtitle = document.getElementById("studioSubtitle");
    const studioStatus = document.getElementById("studioStatus");
    const partSearch = document.getElementById("partSearch");
    const unboundFilter = document.getElementById("unboundFilter");

    function currentPackage() {
      return DATA.templatePackages[state.templateType];
    }

    function activeMapping() {
      return state.customMapping || currentPackage().mapping;
    }

    function setStatus(message) {
      studioStatus.textContent = message;
    }

    function ensureCustomMapping() {
      if (!state.customMapping) {
        state.customMapping = JSON.parse(JSON.stringify(currentPackage().mapping));
      }
      return state.customMapping;
    }

    function renderTemplateSelect() {
      templateSelect.innerHTML = Object.entries(DATA.templatePackages).map(([templateType, pkg]) => `
        <option value="${templateType}" ${templateType === state.templateType ? "selected" : ""}>${pkg.title}</option>
      `).join("");
      templateSelect.onchange = () => {
        state.templateType = templateSelect.value;
        state.selectedPart = null;
        state.customMapping = null;
        renderAll();
      };
    }

    function renderPartGrid() {
      const pkg = currentPackage();
      const query = partSearch.value.trim().toLowerCase();
      const keys = Object.keys(activeMapping()).sort().filter((key) => !query || key.toLowerCase().includes(query));
      if (!state.selectedPart) state.selectedPart = keys[0] || null;
      partGrid.innerHTML = keys.map((key) => `
        <button class="part-btn ${state.selectedPart === key ? "active" : ""}" data-part="${key}">
          ${key} (${(activeMapping()[key] || []).length})
        </button>
      `).join("");
      partGrid.querySelectorAll(".part-btn").forEach((button) => {
        button.addEventListener("click", () => {
          state.selectedPart = button.dataset.part;
          renderAll();
        });
      });
      mappingEditor.value = JSON.stringify(activeMapping(), null, 2);
      studioTitle.textContent = `${pkg.title} · 映射预览`;
      studioSubtitle.textContent = `${pkg.description} 当前共 ${pkg.supportedParts.length} 个已支持部件，SVG 中共 ${pkg.allElementIds.length} 个可识别 id。`;
    }

    function highlightStage() {
      const pkg = currentPackage();
      studioStage.innerHTML = pkg.svgBase;
      const svg = studioStage.querySelector("svg");
      if (!svg) return;
      const mapping = activeMapping();
      svg.querySelectorAll("[id]").forEach((node) => {
        node.style.cursor = "pointer";
        node.addEventListener("mouseenter", () => {
          setStatus(`当前部件：${state.selectedPart || "未选择"} · 悬停元素：${node.id}`);
        });
        node.addEventListener("mouseleave", () => {
          setStatus("点击左侧部件后，可直接点击中间 SVG 元素为该部件增删映射。");
        });
        node.addEventListener("click", () => {
          if (!state.selectedPart || !node.id) return;
          const mappingDraft = ensureCustomMapping();
          const selectedIds = mappingDraft[state.selectedPart] || [];
          const existed = selectedIds.includes(node.id);
          Object.keys(mappingDraft).forEach((partKey) => {
            mappingDraft[partKey] = (mappingDraft[partKey] || []).filter((id) => id !== node.id);
          });
          if (!existed) {
            mappingDraft[state.selectedPart] = [...(mappingDraft[state.selectedPart] || []), node.id];
          }
          mappingEditor.value = JSON.stringify(mappingDraft, null, 2);
          setStatus(`${existed ? "已移除" : "已分配"}元素 ${node.id} ${existed ? "从" : "到"} ${state.selectedPart}`);
          renderAll();
        });
      });
      Object.entries(mapping).forEach(([part, ids]) => {
        ids.forEach((id) => {
          const node = svg.querySelector("#" + CSS.escape(id));
          if (!node) return;
          const selected = part === state.selectedPart;
          if (node.tagName.toLowerCase() === "line") {
            node.style.stroke = selected ? "#1d4ed8" : "#9aa8ba";
            node.style.opacity = selected ? "1" : "0.3";
            node.style.strokeWidth = selected ? "3" : "1.4";
          } else {
            node.style.fill = selected ? "#2f6fe4" : "#d8d8d8";
            node.style.opacity = selected ? "1" : "0.45";
            node.style.stroke = selected ? "#0f172a" : "#bcbcbc";
            node.style.strokeWidth = selected ? "2.1" : "0.969463";
          }
        });
      });
    }

    function renderIdLists() {
      const pkg = currentPackage();
      const mapping = activeMapping();
      const selectedIds = (mapping[state.selectedPart] || []);
      mappedIds.innerHTML = selectedIds.length
        ? selectedIds.map((id) => `<button type="button" data-mapped-id="${id}">${id}</button>`).join("")
        : "<div>当前部件没有绑定的 svg id。</div>";
      const used = new Set(Object.values(mapping).flat());
      const query = unboundFilter.value.trim().toLowerCase();
      const unbound = pkg.allElementIds.filter((id) => !used.has(id) && (!query || id.toLowerCase().includes(query))).slice(0, 80);
      unboundIds.innerHTML = unbound.length
        ? unbound.map((id) => `<button type="button" data-unbound-id="${id}">${id}</button>`).join("")
        : "<div>当前模板没有未绑定 id。</div>";
      mappedIds.querySelectorAll("[data-mapped-id]").forEach((button) => {
        button.addEventListener("click", () => {
          const mappingDraft = ensureCustomMapping();
          mappingDraft[state.selectedPart] = (mappingDraft[state.selectedPart] || []).filter((id) => id !== button.dataset.mappedId);
          mappingEditor.value = JSON.stringify(mappingDraft, null, 2);
          setStatus(`已从 ${state.selectedPart} 中移除 ${button.dataset.mappedId}`);
          renderAll();
        });
      });
      unboundIds.querySelectorAll("[data-unbound-id]").forEach((button) => {
        button.addEventListener("click", () => {
          if (!state.selectedPart) return;
          const mappingDraft = ensureCustomMapping();
          Object.keys(mappingDraft).forEach((partKey) => {
            mappingDraft[partKey] = (mappingDraft[partKey] || []).filter((id) => id !== button.dataset.unboundId);
          });
          mappingDraft[state.selectedPart] = [...(mappingDraft[state.selectedPart] || []), button.dataset.unboundId];
          mappingEditor.value = JSON.stringify(mappingDraft, null, 2);
          setStatus(`已将 ${button.dataset.unboundId} 添加到 ${state.selectedPart}`);
          renderAll();
        });
      });
    }

    document.getElementById("applyMappingBtn").onclick = () => {
      try {
        state.customMapping = JSON.parse(mappingEditor.value);
        if (!state.customMapping[state.selectedPart]) {
          state.selectedPart = Object.keys(state.customMapping)[0] || null;
        }
        renderAll();
      } catch (error) {
        alert("mapping.json 解析失败，请检查 JSON 格式。");
      }
    };

    document.getElementById("resetMappingBtn").onclick = () => {
      state.customMapping = null;
      setStatus("已恢复到模板默认映射。");
      renderAll();
    };

    document.getElementById("formatMappingBtn").onclick = () => {
      try {
        mappingEditor.value = JSON.stringify(JSON.parse(mappingEditor.value), null, 2);
        setStatus("mapping 草案已格式化。");
      } catch (error) {
        alert("当前 mapping 草案不是合法 JSON，无法格式化。");
      }
    };

    document.getElementById("downloadMappingBtn").onclick = () => {
      const blob = new Blob([JSON.stringify(activeMapping(), null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${state.templateType}-mapping.json`;
      a.click();
      URL.revokeObjectURL(url);
      setStatus(`已下载 ${state.templateType}-mapping.json`);
    };

    document.getElementById("copySelectedIdsBtn").onclick = async () => {
      const ids = (activeMapping()[state.selectedPart] || []).join(", ");
      if (!ids) return;
      try {
        await navigator.clipboard.writeText(ids);
        setStatus(`已复制 ${state.selectedPart} 的 ${activeMapping()[state.selectedPart].length} 个 id。`);
      } catch (error) {
        setStatus("当前环境不支持剪贴板写入，请手动复制。");
      }
    };

    mappingEditor.addEventListener("input", () => {
      setStatus("草案已修改，点击“应用映射草案”后刷新预览。");
    });
    partSearch.addEventListener("input", () => renderAll());
    unboundFilter.addEventListener("input", () => renderIdLists());

    function renderAll() {
      renderTemplateSelect();
      renderPartGrid();
      highlightStage();
      renderIdLists();
    }

    renderAll();
  </script>
</body>
</html>
"""
    return template.replace("__STUDIO_DATA_PAYLOAD__", json.dumps(studio_data, ensure_ascii=False))


def _build_dataset_mapper_page(mapper_data: dict) -> str:
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>dataset mapper</title>
  <style>
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: #f5f7fb;
      color: #1f2937;
    }
    * { box-sizing: border-box; }
    .shell { width: min(1500px, calc(100vw - 32px)); margin: 24px auto; display: grid; gap: 16px; }
    .card {
      background: rgba(255,255,255,0.94);
      border-radius: 24px;
      border: 1px solid rgba(255,255,255,0.76);
      box-shadow: 0 20px 60px rgba(15,23,42,0.08);
      padding: 22px;
    }
    .hero { display:flex; justify-content:space-between; gap:20px; }
    .muted { color:#6b7280; font-size:13px; line-height:1.65; }
    .layout { display:grid; grid-template-columns: 1fr 1fr 360px; gap:16px; }
    textarea, select, button, input[type="search"] {
      width: 100%;
      font: inherit;
      border-radius: 14px;
      border: 1px solid #d8dde6;
    }
    textarea {
      min-height: 520px;
      padding: 14px;
      resize: vertical;
      background: #fbfcff;
      line-height: 1.55;
    }
    select, button {
      padding: 12px 14px;
      background:#fff;
    }
    input[type="search"] {
      padding: 12px 14px;
      background:#fff;
    }
    .toolbar { display:flex; gap:10px; flex-wrap:wrap; margin-top: 12px; }
    .toolbar button { width:auto; cursor:pointer; }
    .toolbar input[type="search"] { max-width: 240px; }
    .summary {
      display:grid;
      gap: 10px;
      margin-top: 14px;
    }
    .summary div {
      padding: 12px;
      border-radius: 16px;
      background: rgba(15,23,42,0.03);
      border: 1px solid rgba(15,23,42,0.04);
      font-size: 13px;
    }
    .tag {
      display:inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background:#eef6ff;
      color:#2952c3;
      font-size: 12px;
      margin-bottom: 8px;
    }
    .status {
      margin-top: 12px;
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(47,111,228,0.08);
      color:#2952c3;
      font-size: 12px;
      line-height: 1.6;
    }
    @media (max-width: 1180px) { .layout { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="shell">
    <section class="card hero">
      <div>
        <div class="tag">Phase 3 · dataset mapper</div>
        <h1 style="margin:8px 0 0;">数据适配器工作台</h1>
        <p class="muted">该页面用于把新数据源套进标准模板协议。左侧输入源数据 JSON，中间输入字段映射规则，点击转换后即可得到 engine 可消费的标准 payload。</p>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;">
        <a class="tag" href="./index.html">返回 Engine</a>
        <a class="tag" href="./template_studio.html">打开 Studio</a>
      </div>
    </section>
    <section class="card">
      <label class="muted">预设规则</label>
      <div style="margin-top:8px;">
        <select id="presetSelect"></select>
      </div>
      <div class="toolbar">
        <button id="loadPresetBtn">加载预设</button>
        <button id="mapBtn">映射为标准 payload</button>
        <button id="formatBtn">格式化输入</button>
        <button id="copyOutputBtn">复制结果</button>
        <button id="downloadBtn">下载结果</button>
      </div>
      <div class="status" id="mapperStatus">支持直接修改源数据与规则 JSON，点击映射后可查看模板覆盖率与未映射部件。</div>
    </section>
    <section class="layout">
      <div class="card">
        <h2>源数据 JSON</h2>
        <textarea id="sourceEditor"></textarea>
      </div>
      <div class="card">
        <h2>字段映射规则</h2>
        <textarea id="rulesEditor"></textarea>
      </div>
      <div class="card">
        <h2>映射结果摘要</h2>
        <div class="summary" id="summary"></div>
        <h2 style="margin-top:18px;">标准 Payload</h2>
        <textarea id="outputEditor" style="min-height:360px;"></textarea>
      </div>
    </section>
  </div>
  <script>
    window.__MAPPER_DATA__ = __MAPPER_DATA_PAYLOAD__;
  </script>
  <script>
    const DATA = window.__MAPPER_DATA__;
    const presetSelect = document.getElementById("presetSelect");
    const sourceEditor = document.getElementById("sourceEditor");
    const rulesEditor = document.getElementById("rulesEditor");
    const outputEditor = document.getElementById("outputEditor");
    const summary = document.getElementById("summary");
    const mapperStatus = document.getElementById("mapperStatus");

    function setStatus(message) {
      mapperStatus.textContent = message;
    }

    function slugify(value) {
      return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    }

    function getByPath(obj, path) {
      if (!path) return undefined;
      return String(path).split(".").reduce((acc, key) => acc && typeof acc === "object" ? acc[key] : undefined, obj);
    }

    function inferBikeType(record) {
      const text = [record.bike_name, record.brand, record.description, record.official_url, record.bikeType].filter(Boolean).join(" ").toLowerCase();
      if (/(mountain|mtb|trail|enduro|downhill|xc|one-sixty|one-forty|ninety-six|spectral|neuron|torque)/.test(text)) return "mountain";
      if (/(fold|brompton|dahon|fnhon|oyama)/.test(text)) return "folding";
      if (/(gravel|silex)/.test(text)) return "gravel";
      if (/(road|race|endurance|aero|madone|domane|endurace)/.test(text)) return "road";
      return "other";
    }

    function templateTypeForBikeType(type) {
      return type === "mountain" ? "mountain" : "road";
    }

    function mapGeneric(records, ruleSet) {
      const partAliases = Object.fromEntries(Object.entries(ruleSet.partMappings || {}).map(([key, value]) => [String(key).toLowerCase(), String(value).toLowerCase()]));
      return records.map((record) => {
        const bikeName = getByPath(record, ruleSet.bikeNameField) || "External Bike";
        const brand = getByPath(record, ruleSet.brandField) || "external";
        const bikeType = getByPath(record, ruleSet.bikeTypeField) || inferBikeType(record);
        const parts = (getByPath(record, ruleSet.partsPath) || []).map((part) => {
          const rawKey = String(getByPath(part, ruleSet.partKeyField) || part.part_key || "").toLowerCase();
          const partKey = partAliases[rawKey] || rawKey;
          return {
            partKey,
            componentName: getByPath(part, ruleSet.componentNameField) || part.component_name || part.name || null,
            metrics: {
              price_score: getByPath(part, ruleSet.metricMappings.price_score) ?? null,
              quality_score: getByPath(part, ruleSet.metricMappings.quality_score) ?? null,
              value_score: getByPath(part, ruleSet.metricMappings.value_score) ?? null
            },
            sourceType: "observed",
            templateLabels: DATA.partFromApi[partKey] || [],
            evidence: {
              offersCount: Number(getByPath(part, ruleSet.offersCountField) || part.offers_count || 0),
              reviewsCount: Number(getByPath(part, ruleSet.reviewsCountField) || part.reviews_count || 0),
              confidence: 0.7,
              coverage: "medium"
            },
            render: {
              status: (DATA.partFromApi[partKey] || []).length ? "mapped" : "template_missing",
              fillValue: null,
              fillColor: "#d9dde3",
              strokeOpacity: 0.45
            },
            displayName: partKey.replace(/_/g, " ").replace(/(^|\\s)\\S/g, (m) => m.toUpperCase())
          };
        }).filter((part) => part.partKey);
        return {
          schemaVersion: "1.0.0",
          bikeId: slugify(`${brand}-${bikeName}`),
          bikeName,
          brand,
          bikeType,
          templateType: templateTypeForBikeType(String(bikeType).toLowerCase()),
          views: {
            front: null,
            side: getByPath(record, ruleSet.sideViewField) || null,
            rear: null
          },
          availableModes: ["price_score", "quality_score", "value_score"],
          defaultMode: "price_score",
          parts,
          summary: {
            partsCount: parts.length,
            mappedPartsCount: parts.filter((part) => part.templateLabels.length).length,
            templateCoverage: parts.length ? Number((parts.filter((part) => part.templateLabels.length).length / parts.length).toFixed(2)) : 0
          },
          meta: {
            source: ruleSet.sourceName || "generic"
          }
        };
      });
    }

    function summarizeMapped(mapped) {
      const first = mapped[0] || { summary: { partsCount: 0, mappedPartsCount: 0, templateCoverage: 0 }, templateType: "road", parts: [] };
      const unmapped = [...new Set((first.parts || []).filter((part) => !part.templateLabels.length).map((part) => part.partKey))];
      summary.innerHTML = `
        <div><b>输出记录数</b><br>${mapped.length}</div>
        <div><b>首条 templateType</b><br>${first.templateType}</div>
        <div><b>首条部件数</b><br>${first.summary.partsCount}</div>
        <div><b>首条已映射数</b><br>${first.summary.mappedPartsCount}</div>
        <div><b>首条模板覆盖率</b><br>${Math.round((first.summary.templateCoverage || 0) * 100)}%</div>
        <div><b>首条未映射部件</b><br>${unmapped.length ? unmapped.join(", ") : "无"}</div>
      `;
    }

    function loadPreset(name) {
      const preset = DATA.presets[name];
      sourceEditor.value = JSON.stringify(preset.source, null, 2);
      rulesEditor.value = JSON.stringify(preset.rules, null, 2);
      outputEditor.value = JSON.stringify(preset.exampleOutput, null, 2);
      summarizeMapped(preset.exampleOutput);
      setStatus(`已加载预设 ${name}，可直接修改后重新映射。`);
    }

    presetSelect.innerHTML = Object.keys(DATA.presets).map((key) => `<option value="${key}">${key}</option>`).join("");
    document.getElementById("loadPresetBtn").onclick = () => loadPreset(presetSelect.value);
    document.getElementById("mapBtn").onclick = () => {
      try {
        const source = JSON.parse(sourceEditor.value);
        const rules = JSON.parse(rulesEditor.value);
        const sourceList = Array.isArray(source) ? source : [source];
        const mapped = mapGeneric(sourceList, rules);
        outputEditor.value = JSON.stringify(mapped, null, 2);
        summarizeMapped(mapped);
        setStatus(`映射完成，共输出 ${mapped.length} 条记录。`);
      } catch (error) {
        alert("映射失败，请检查源数据或规则 JSON 格式。");
        setStatus("映射失败，请先修正 JSON 格式或字段路径。");
      }
    };
    document.getElementById("formatBtn").onclick = () => {
      try {
        sourceEditor.value = JSON.stringify(JSON.parse(sourceEditor.value), null, 2);
        rulesEditor.value = JSON.stringify(JSON.parse(rulesEditor.value), null, 2);
        setStatus("源数据与规则 JSON 已格式化。");
      } catch (error) {
        alert("格式化失败，请先修正 JSON。");
      }
    };
    document.getElementById("copyOutputBtn").onclick = async () => {
      try {
        await navigator.clipboard.writeText(outputEditor.value);
        setStatus("已复制标准 payload 到剪贴板。");
      } catch (error) {
        setStatus("当前环境不支持剪贴板写入，请手动复制。");
      }
    };
    document.getElementById("downloadBtn").onclick = () => {
      const blob = new Blob([outputEditor.value], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "mapped-bike-payload.json";
      a.click();
      URL.revokeObjectURL(url);
      setStatus("已下载 mapped-bike-payload.json");
    };
    [sourceEditor, rulesEditor].forEach((editor) => {
      editor.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
          document.getElementById("mapBtn").click();
        }
      });
    });
    loadPreset(Object.keys(DATA.presets)[0]);
  </script>
</body>
</html>
"""
    return template.replace("__MAPPER_DATA_PAYLOAD__", json.dumps(mapper_data, ensure_ascii=False))


def _legacy_showcase_summary(visual_dir: Path, template_packages: dict[str, dict], catalog: dict[str, object]) -> dict[str, object]:
    return {
        "output_path": str(visual_dir / "index.html"),
        "inkscape_detected": False,
        "exported_pngs": [],
        "template_variants": {
            template_type: package["mapping"]
            for template_type, package in template_packages.items()
        },
        "showcase_bike_count": len(catalog["bikes"]),
        "default_bike_id": catalog["defaultBikeId"],
    }


def _engine_runtime_summary(visual_dir: Path, template_packages: dict[str, dict], catalog: dict[str, object]) -> dict[str, object]:
    return {
        "runtime_output": str(visual_dir / "index.html"),
        "studio_output": str(visual_dir / "template_studio.html"),
        "mapper_output": str(visual_dir / "dataset_mapper.html"),
        "template_packages": {
            template_type: {
                "title": package["title"],
                "supported_parts": package["supportedParts"],
                "mapping": package["mapping"],
            }
            for template_type, package in template_packages.items()
        },
        "bike_count": len(catalog["bikes"]),
        "default_bike_id": catalog["defaultBikeId"],
    }


def build_suite(
    visual_subdir: str = "bike_template_engine",
    write_legacy_showcase_summary: bool = False,
) -> dict[str, object]:
    exports_dir = ROOT / "data" / "gold" / "exports"
    visual_dir = ROOT / "data" / "visualizations" / "bike_template_engine"
    template_package_dir = ROOT / "data" / "template_packages"
    if visual_subdir != "bike_template_engine":
        visual_dir = ROOT / "data" / "visualizations" / visual_subdir

    bikes_api = _read_json(exports_dir / "website_bikes_api.json")
    initial_catalog = build_bike_catalog(bikes_api, {})
    example_bikes = _bike_options_by_template(initial_catalog["bikes"])
    template_packages = load_template_packages(example_bikes)
    catalog = build_bike_catalog(bikes_api, template_packages)

    render_states_by_bike: dict[str, dict[str, dict]] = {}
    for bike in catalog["bikes"]:
        render_states_by_bike[bike["bikeId"]] = {
            mode: build_render_state(bike, template_packages, mode)
            for mode in MODE_META
        }

    engine_payload_path = exports_dir / "bike_template_engine_payloads.json"
    engine_payload_path.write_text(json.dumps(catalog["bikes"], ensure_ascii=False, indent=2), encoding="utf-8")

    written_template_files = write_template_package_artifacts(template_package_dir, template_packages)

    engine_data = {
        "modes": MODE_META,
        "defaultBikeId": catalog["defaultBikeId"],
        "bikeOptions": catalog["bikeOptions"],
        "templatePackages": {
            key: {
                "title": value["title"],
                "description": value["description"],
                "mapping": value["mapping"],
                "svgBase": value["svgBase"],
                "supportedParts": value["supportedParts"],
            }
            for key, value in template_packages.items()
        },
        "rendersByBikeId": render_states_by_bike,
        "matrix": build_template_matrix(catalog["bikes"]),
    }

    studio_data = {
        "defaultTemplateType": "mountain",
        "templatePackages": template_packages,
    }

    generic_source = [
        {
            "name": "Demo Trail Bike",
            "brand_name": "demo",
            "category": "mountain",
            "views": {"side": "https://example.com/demo-trail-bike-side.jpg"},
            "components": [
                {"slot": "fork", "name": "Fox 36 Factory", "price": 469, "quality": 0.92, "value": 0.31, "offers": 4, "reviews": 3},
                {"slot": "shock", "name": "RockShox Super Deluxe", "price": 245, "quality": 0.88, "value": 0.29, "offers": 2, "reviews": 5},
                {"slot": "tyre", "name": "Maxxis Minion DHF", "price": 52, "quality": 0.86, "value": 0.34, "offers": 5, "reviews": 6},
            ],
        }
    ]
    generic_rules = {
        "sourceName": "generic_demo",
        "bikeNameField": "name",
        "brandField": "brand_name",
        "bikeTypeField": "category",
        "sideViewField": "views.side",
        "partsPath": "components",
        "partKeyField": "slot",
        "componentNameField": "name",
        "offersCountField": "offers",
        "reviewsCountField": "reviews",
        "metricMappings": {
            "price_score": "price",
            "quality_score": "quality",
            "value_score": "value",
        },
        "partMappings": {
            "wheel": "tyre",
            "rearshockabsorber": "shock",
            "seat post": "seatpost",
        },
    }

    mapper_data = {
        "partFromApi": PART_FROM_API,
        "presets": {
            "generic_demo": {
                "source": generic_source,
                "rules": generic_rules,
                "exampleOutput": map_generic_dataset(generic_source, generic_rules),
            },
            "website_api_shape": {
                "source": bikes_api[:1],
                "rules": {
                    "sourceName": "website_api_shape",
                    "bikeNameField": "bike_name",
                    "brandField": "brand",
                    "bikeTypeField": "bike_type",
                    "sideViewField": "views.side",
                    "partsPath": "parts",
                    "partKeyField": "part_key",
                    "componentNameField": "component_name",
                    "offersCountField": "offers_count",
                    "reviewsCountField": "reviews_count",
                    "metricMappings": {
                        "price_score": "price_score",
                        "quality_score": "quality_score",
                        "value_score": "value_score",
                    },
                    "partMappings": {},
                },
                "exampleOutput": map_generic_dataset(
                    bikes_api[:1],
                    {
                        "sourceName": "website_api_shape",
                        "bikeNameField": "bike_name",
                        "brandField": "brand",
                        "bikeTypeField": "bike_type",
                        "sideViewField": "views.side",
                        "partsPath": "parts",
                        "partKeyField": "part_key",
                        "componentNameField": "component_name",
                        "offersCountField": "offers_count",
                        "reviewsCountField": "reviews_count",
                        "metricMappings": {
                            "price_score": "price_score",
                            "quality_score": "quality_score",
                            "value_score": "value_score",
                        },
                        "partMappings": {},
                    },
                ),
            },
        },
    }

    _write_text(visual_dir / "index.html", _build_engine_page(engine_data))
    _write_text(visual_dir / "template_studio.html", _build_template_studio_page(studio_data))
    _write_text(visual_dir / "dataset_mapper.html", _build_dataset_mapper_page(mapper_data))

    summary = {
        "engine_output": str(visual_dir / "index.html"),
        "template_studio_output": str(visual_dir / "template_studio.html"),
        "dataset_mapper_output": str(visual_dir / "dataset_mapper.html"),
        "engine_payload_output": str(engine_payload_path),
        "template_package_dir": str(template_package_dir),
        "template_package_files": written_template_files,
        "bike_count": len(catalog["bikes"]),
        "default_bike_id": catalog["defaultBikeId"],
    }
    _write_text(visual_dir / "suite_summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    _write_text(
        visual_dir / "engine_runtime_summary.json",
        json.dumps(_engine_runtime_summary(visual_dir, template_packages, catalog), ensure_ascii=False, indent=2),
    )
    if write_legacy_showcase_summary:
        legacy_summary = _legacy_showcase_summary(visual_dir, template_packages, catalog)
        _write_text(visual_dir / "showcase_summary.json", json.dumps(legacy_summary, ensure_ascii=False, indent=2))
        summary["legacy_alias_summary"] = str(visual_dir / "showcase_summary.json")
    return summary


def main() -> None:
    summary = build_suite()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
