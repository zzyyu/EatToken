// EatToken frontend — minimal vanilla JS, no build step

const TRANSLATIONS = {
  en: {
    app_title: "EatToken",
    app_subtitle: "Rapidly consume LLM API tokens",
    form_api_url: "API URL",
    form_api_key: "API Key",
    form_provider: "Provider",
    form_model: "Model",
    form_target_tokens: "Target Tokens",
    form_context_size: "Context Size Override",
    form_max_input: "Request Size",
    form_max_output: "Max Output Tokens",
    form_request_timeout: "Request Timeout",
    form_concurrency: "Concurrency Override",
    form_optional: "(optional)",
    form_auto_detect: "Auto-detect",
    provider_auto: "Auto Detect",
    placeholder_api_url: "https://api.openai.com/v1",
    placeholder_api_key: "sk-...",
    placeholder_model: "gpt-4o",
    placeholder_target_tokens: "Leave empty to run until stopped",
    placeholder_context_size: "Auto from model registry (override if needed)",
    placeholder_max_input: "1024 tokens per request",
    placeholder_max_output: "256 tokens per response",
    placeholder_request_timeout: "30 seconds",
    placeholder_concurrency: "Adaptive: starts at 1 and increases",
    button_start: "Start",
    button_stop: "Stop",
    button_switch_lang: "中文",
    progress_consumed: "Consumed",
    progress_target: "Target",
    progress_qps: "QPS",
    progress_in_flight: "In flight",
    progress_success: "Success",
    progress_failed: "Failed",
    progress_elapsed: "Elapsed",
    status_ready: "Ready.",
    status_running: "Running...",
    status_done: "Done.",
    status_error: "Error",
    label_language: "Language",
    advanced_options: "Advanced Options",
    panel_kicker: "LIVE RUN",
    panel_title: "Runtime",
    panel_subtitle: "Usage, throughput and request logs",
    progress_label: "Progress",
    logs_title: "Request log",
    logs_empty: "No run yet. Configure a provider and start when ready.",
    progress_infinite: "Infinite",
    status_stopping: "Stopping...",
  },
  zh: {
    app_title: "EatToken",
    app_subtitle: "快速消耗 LLM API token",
    form_api_url: "API 地址",
    form_api_key: "API Key",
    form_provider: "协议类型",
    form_model: "模型名称",
    form_target_tokens: "目标 Token 数",
    form_context_size: "上下文长度覆盖",
    form_max_input: "单个请求大小",
    form_max_output: "单次最大输出",
    form_request_timeout: "单请求超时",
    form_concurrency: "并发数覆盖",
    form_optional: "（选填）",
    form_auto_detect: "自动探测",
    provider_auto: "自动探测",
    placeholder_api_url: "https://api.openai.com/v1",
    placeholder_api_key: "sk-...",
    placeholder_model: "gpt-4o",
    placeholder_target_tokens: "留空则持续运行，直到手动停止",
    placeholder_context_size: "默认从模型注册表探测，需要时手动覆盖",
    placeholder_max_input: "每个请求默认 1024 Token",
    placeholder_max_output: "每次响应默认最多 256 Token",
    placeholder_request_timeout: "默认 30 秒",
    placeholder_concurrency: "自适应：从 1 开始逐步增加",
    button_start: "开始消耗",
    button_stop: "停止",
    button_switch_lang: "English",
    progress_consumed: "已消耗",
    progress_target: "目标",
    progress_qps: "QPS",
    progress_in_flight: "请求中",
    progress_success: "成功",
    progress_failed: "失败",
    progress_elapsed: "运行时间",
    status_ready: "就绪。",
    status_running: "运行中...",
    status_done: "完成。",
    status_error: "错误",
    label_language: "语言",
    advanced_options: "高级选项",
    panel_kicker: "实时任务",
    panel_title: "运行情况",
    panel_subtitle: "用量、吞吐和请求日志",
    progress_label: "运行进度",
    logs_title: "请求日志",
    logs_empty: "暂无运行记录，完成左侧配置后即可开始。",
    progress_infinite: "无限运行",
    status_stopping: "正在停止...",
  },
};

let currentLang = "en";
let currentRunId = null;
let eventSource = null;
let serverTranslations = null;
let lastLogId = 0;

function $(id) { return document.getElementById(id); }

function formatNumber(n) {
  return n.toLocaleString(currentLang === "zh" ? "zh-CN" : "en-US");
}

function translate(key) {
  const dict = (serverTranslations && serverTranslations[currentLang]) || TRANSLATIONS[currentLang] || TRANSLATIONS.en;
  return dict[key] || key;
}

function applyTranslations(lang) {
  currentLang = lang;
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  const dict = (serverTranslations && serverTranslations[lang]) || TRANSLATIONS[lang] || TRANSLATIONS.en;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (dict[key]) {
      el.textContent = dict[key];
    }
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (dict[key]) {
      el.placeholder = dict[key];
    }
  });
  const toggle = $("lang-toggle");
  if (toggle) {
    toggle.textContent = lang === "en" ? "中文" : "English";
  }
}

async function detectLang() {
  if (window.__I18N__) {
    serverTranslations = window.__I18N__;
    const saved = localStorage.getItem("eattoken-language");
    const browserLang = (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
    const lang = saved || browserLang || window.__I18N_LANG__ || "en";
    applyTranslations(lang);
    return;
  }
  // Fallback to API
  try {
    const res = await fetch("/api/lang");
    const data = await res.json();
    applyTranslations(data.lang);
  } catch {
    applyTranslations("en");
  }
}

async function toggleLang() {
  const newLang = currentLang === "en" ? "zh" : "en";
  try {
    await fetch("/api/lang", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({lang: newLang}),
    });
  } catch {
    // ignore network errors
  }
  localStorage.setItem("eattoken-language", newLang);
  applyTranslations(newLang);
}

function showProgress(show) {
  $("progress").classList.toggle("has-run", show);
}

function setStatus(key, state = "") {
  const chip = $("status-chip");
  chip.dataset.i18n = key;
  chip.textContent = translate(key);
  chip.classList.toggle("is-running", state === "running");
  chip.classList.toggle("is-error", state === "error");
  document.querySelector(".runtime-panel").classList.toggle("is-running", state === "running");
}

function updateStats(data) {
  $("stat-consumed").textContent = formatNumber(data.total_tokens);
  $("stat-target").textContent = data.target != null ? formatNumber(data.target) : "∞";
  $("stat-qps").textContent = data.qps.toFixed(1);
  $("stat-in-flight").textContent = formatNumber(data.in_flight || 0);
  $("stat-success").textContent = formatNumber(data.total_requests - data.failed_requests);
  $("stat-failed").textContent = formatNumber(data.failed_requests);
  $("stat-elapsed").textContent = data.elapsed.toFixed(1) + "s";

  const hasTarget = data.target != null;
  const pct = hasTarget ? Math.min(100, (data.total_tokens / data.target) * 100) : 0;
  const isInfinite = !hasTarget && data.running;
  $("progress-bar").classList.toggle("is-indeterminate", isInfinite);
  if (isInfinite) {
    $("progress-fill").style.removeProperty("width");
  } else {
    $("progress-fill").style.width = hasTarget ? pct + "%" : "0%";
  }
  $("progress-label").textContent = hasTarget ? pct.toFixed(1) + "%" : "∞";

  if (data.error) {
    setStatus("status_error", "error");
  } else if (data.running) {
    setStatus("status_running", "running");
  } else {
    setStatus("status_done");
  }
}

function appendLog(msg, timestamp = null, level = "info") {
  const log = $("log");
  const line = document.createElement("div");
  line.className = level === "error" ? "log-line is-error" : "log-line";
  line.textContent = `[${timestamp || new Date().toLocaleTimeString()}] ${msg}`;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

function appendServerLogs(entries = []) {
  for (const entry of entries) {
    if (entry.id <= lastLogId) continue;
    appendLog(entry.message, entry.time, entry.level);
    lastLogId = entry.id;
  }
}

function hydrateForm(config) {
  if (!config) return;
  const form = $("config-form");
  for (const [name, value] of Object.entries(config)) {
    if (value == null || name === "api_key") continue;
    const control = form.elements.namedItem(name);
    if (control) control.value = String(value);
  }
}

function scrollToResults() {
  if (!window.matchMedia("(max-width: 980px)").matches) return;
  const progress = $("progress");
  const log = $("log");
  if (progress) progress.scrollIntoView({behavior: "smooth", block: "start"});
  if (log) setTimeout(() => log.scrollIntoView({behavior: "smooth", block: "end"}), 300);
}

function subscribeToRun(runId) {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  const source = new EventSource(`/events/${runId}?after_log_id=${lastLogId}`);
  eventSource = source;
  source.addEventListener("progress", (e) => {
    const data = JSON.parse(e.data);
    updateStats(data);
    appendServerLogs(data.logs);
  });
  source.addEventListener("done", (e) => {
    const data = JSON.parse(e.data);
    updateStats(data);
    appendServerLogs(data.logs);
    source.close();
    if (eventSource === source) eventSource = null;
    toggleButtons(false);
    scrollToResults();
  });
  source.onerror = () => {
    if (eventSource !== source) return;
    appendLog("Connection error", null, "error");
    setStatus("status_error", "error");
    source.close();
    eventSource = null;
    toggleButtons(false);
  };
}

async function restoreCurrentRun() {
  try {
    const response = await fetch("/api/run/current");
    if (!response.ok) return;
    const {run} = await response.json();
    if (!run) return;

    currentRunId = run.run_id;
    hydrateForm(run.config);
    showProgress(true);
    $("log").textContent = "";
    lastLogId = 0;
    updateStats(run);
    appendServerLogs(run.logs);
    toggleButtons(run.running);
    if (run.running) subscribeToRun(run.run_id);
  } catch (err) {
    appendLog("Failed to restore run: " + err.message, null, "error");
  }
}

async function startRun(formData) {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  const form = new FormData();
  form.append("api_url", formData.api_url);
  form.append("api_key", formData.api_key);
  form.append("provider", formData.provider);
  form.append("model", formData.model);
  if (formData.target_tokens) form.append("target_tokens", formData.target_tokens);
  if (formData.context_size) form.append("context_size", formData.context_size);
  if (formData.max_input_tokens) form.append("max_input_tokens", formData.max_input_tokens);
  if (formData.max_output_tokens) form.append("max_output_tokens", formData.max_output_tokens);
  if (formData.request_timeout_seconds) form.append("request_timeout_seconds", formData.request_timeout_seconds);
  if (formData.concurrency) form.append("concurrency", formData.concurrency);

  try {
    const res = await fetch("/run", {method: "POST", body: form});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || "Failed");
    currentRunId = data.run_id;
    showProgress(true);
    $("log").textContent = "";
    lastLogId = 0;
    updateStats(data.run);
    appendServerLogs(data.run.logs);
    scrollToResults();
    toggleButtons(true);
    subscribeToRun(currentRunId);
  } catch (err) {
    appendLog("Error: " + err.message);
    setStatus("status_error", "error");
    toggleButtons(false);
  }
}

function toggleButtons(running) {
  const btnStart = $("btn-start");
  const btnStop = $("btn-stop");
  if (btnStart) btnStart.style.display = running ? "none" : "inline-block";
  if (btnStop) btnStop.style.display = running ? "inline-block" : "none";
  if (btnStop && !running) btnStop.disabled = false;
}

document.addEventListener("DOMContentLoaded", async () => {
  await detectLang();
  await restoreCurrentRun();

  $("lang-toggle").addEventListener("click", toggleLang);

  $("config-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const data = Object.fromEntries(fd.entries());
    startRun(data);
  });

  const btnStop = $("btn-stop");
  if (btnStop) {
    btnStop.addEventListener("click", async () => {
      if (!currentRunId) return;
      btnStop.disabled = true;
      try {
        const res = await fetch(`/stop/${currentRunId}`, {method: "POST"});
        if (!res.ok) throw new Error("Stop request failed");
        setStatus("status_stopping", "running");
      } catch (err) {
        appendLog("Error: " + err.message);
        btnStop.disabled = false;
      }
    });
  }
});
