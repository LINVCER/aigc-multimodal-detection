/**
 * ImageNious Popup — 弹出窗交互逻辑
 */

const statusEl = document.getElementById("status");
const detectBtn = document.getElementById("detectBtn");
const clearBtn = document.getElementById("clearBtn");
const openWebBtn = document.getElementById("openWebBtn");

detectBtn.addEventListener("click", async () => {
  statusEl.style.display = "block";
  statusEl.className = "status loading";
  statusEl.innerHTML = "🔄 正在检测当前页面...";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const result = await chrome.tabs.sendMessage(tab.id, { action: "detect_page" });

    if (result.status === "skip") {
      statusEl.className = "status error";
      statusEl.innerHTML = result.message;
    } else if (result.is_ai_generated) {
      statusEl.className = "status ai";
      statusEl.innerHTML = `
        <div>⚠️ 疑似 AI 生成</div>
        <div class="confidence">${(result.confidence * 100).toFixed(0)}%</div>
        <div style="font-size:12px">可疑片段已高亮标注</div>
      `;
    } else {
      statusEl.className = "status human";
      statusEl.innerHTML = `
        <div>✅ 可能为人类写作</div>
        <div class="confidence">${((1 - result.confidence) * 100).toFixed(0)}%</div>
      `;
    }
  } catch (e) {
    statusEl.className = "status error";
    statusEl.innerHTML = "❌ 检测失败：请刷新页面后重试，或确认后端服务已启动";
  }
});

clearBtn.addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  await chrome.tabs.sendMessage(tab.id, { action: "clear_highlights" });
  statusEl.style.display = "none";
});

openWebBtn.addEventListener("click", () => {
  chrome.tabs.create({ url: "http://localhost:5173" });
});
