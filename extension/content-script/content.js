/**
 * ImageNious Content Script
 * 功能: 抓取网页文本 → 发送 API → 高亮标注疑似 AI 片段
 */

const API_BASE = "http://localhost:8000/api/v1";

// 监听 popup 的消息
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "detect_page") {
    detectCurrentPage().then(sendResponse);
    return true; // 保持消息通道开放
  }
  if (msg.action === "clear_highlights") {
    clearHighlights();
    sendResponse({ status: "ok" });
  }
});

/**
 * 提取当前页面的主要文本内容
 */
function extractPageText() {
  // 跳过脚本、样式、导航等
  const skipTags = ["SCRIPT", "STYLE", "NAV", "HEADER", "FOOTER", "NOSCRIPT"];
  const mainContent = document.querySelector("article, main, .content, .post, .article")
    || document.body;

  const walker = document.createTreeWalker(
    mainContent,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode: (node) => {
        if (skipTags.includes(node.parentElement?.tagName)) return NodeFilter.FILTER_REJECT;
        if (!node.textContent.trim()) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    }
  );

  const texts = [];
  while (walker.nextNode()) {
    texts.push({
      text: walker.currentNode.textContent.trim(),
      node: walker.currentNode,
    });
  }
  return texts;
}

/**
 * 检测当前页面
 */
async function detectCurrentPage() {
  const texts = extractPageText();
  const content = texts.map((t) => t.text).join("\n");

  if (!content || content.length < 20) {
    return { status: "skip", message: "页面文本内容不足" };
  }

  try {
    const resp = await fetch(`${API_BASE}/detect/text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, options: { explain: true, attribution: true } }),
    });
    const data = await resp.json();

    if (data.status === "completed" && data.result.is_ai_generated) {
      // 高亮标注
      highlightSuspiciousSpans(data.result.explanation?.suspicious_spans || []);
    }

    return {
      status: "ok",
      is_ai_generated: data.result?.is_ai_generated || false,
      confidence: data.result?.confidence || 0,
    };
  } catch (e) {
    return { status: "error", message: "API 连接失败，请确认后端服务已启动" };
  }
}

/**
 * 高亮标注可疑片段
 */
function highlightSuspiciousSpans(spans) {
  if (!spans.length) return;

  // 获取所有文本节点
  const walker = document.createTreeWalker(
    document.body,
    NodeFilter.SHOW_TEXT,
    null
  );

  while (walker.nextNode()) {
    const node = walker.currentNode;
    const text = node.textContent;

    for (const span of spans) {
      const idx = text.indexOf(span.detail?.split(": ")[1] || "");
      if (idx >= 0 && span.score > 0.6) {
        const wrapper = document.createElement("mark");
        wrapper.className = "imagenious-highlight";
        wrapper.title = `${span.reason}: ${span.detail || ""}`;
        wrapper.dataset.score = span.score;

        // 颜色: 高风险红色，中等橙色
        wrapper.style.backgroundColor = span.score > 0.8
          ? "rgba(239, 68, 68, 0.3)"
          : "rgba(245, 158, 11, 0.3)";

        const range = document.createRange();
        range.setStart(node, idx);
        range.setEnd(node, idx + (span.end - span.start));
        range.surroundContents(wrapper);
        break;
      }
    }
  }
}

/**
 * 清除所有高亮
 */
function clearHighlights() {
  document.querySelectorAll(".imagenious-highlight").forEach((el) => {
    const parent = el.parentNode;
    while (el.firstChild) {
      parent.insertBefore(el.firstChild, el);
    }
    parent.removeChild(el);
  });
}
