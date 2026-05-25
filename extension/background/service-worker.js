/**
 * AIGC--多模态检测 Background Service Worker
 * 处理跨域 API 请求和缓存管理
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log("AIGC--多模态检测 浏览器插件已安装");
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "api_request") {
    fetch(msg.url, {
      method: msg.method || "GET",
      headers: msg.headers || {},
      body: msg.body,
    })
      .then((r) => r.json())
      .then((data) => sendResponse({ status: "ok", data }))
      .catch((e) => sendResponse({ status: "error", message: e.message }));
    return true;
  }
});
