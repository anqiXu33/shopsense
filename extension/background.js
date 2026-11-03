/* ShopSense background service worker
 * 职责：① 转发快捷键 ② 收到抓取数据后，优先调用后端解读；后端不可用则本地兜底生成摘要。
 * 兜底逻辑保证：即使后端没启动，插件也能跑通"抓取 → 语音播报"。
 */

// ── 快捷键 Alt+V → 通知当前标签页的 content script 激活 ──────────────
chrome.commands.onCommand.addListener((command) => {
  if (command !== "activate-shopsense") return;
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]?.id != null) {
      chrome.tabs.sendMessage(tabs[0].id, { type: "ACTIVATE" });
    }
  });
});

// ── 主处理：ASK ─────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== "ASK") return;

  handleAsk(msg.data)
    .then((answer) => sendResponse({ answer, source: "backend" }))
    .catch(() => sendResponse({ answer: localSummary(msg.data), source: "local" }));

  return true; // 异步响应
});

async function handleAsk(data) {
  const { backendUrl } = await chrome.storage.sync.get({ backendUrl: "" });
  if (!backendUrl) throw new Error("no backend configured");

  // 给现有/未来后端预留的接口；超时则走兜底
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 12000);
  try {
    const r = await fetch(`${backendUrl.replace(/\/$/, "")}/api/extension_query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        asin: data.asin,
        title: data.title,
        brand: data.brand,
        price: data.price,
        description: data.description,
        bullets: data.bullets,
        reviews: data.reviews,
        image_url: data.imageUrl,
        question: "Describe this product and flag anything that does not add up.",
      }),
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error("backend " + r.status);
    const json = await r.json();
    if (!json.answer) throw new Error("empty answer");
    return json.answer;
  } finally {
    clearTimeout(timer);
  }
}

// ── 本地兜底：无后端时，用抓到的数据拼一段 TTS 友好的解读 ──────────────
function localSummary(data) {
  const parts = [];

  if (data.title) parts.push(`商品名称：${data.title}。`);
  if (data.price) parts.push(`价格 ${data.price.replace(/[$€£]/g, "")}。`);

  if (data.bullets?.length) {
    parts.push(`官方要点：${data.bullets.slice(0, 3).join("；")}。`);
  }

  const n = data.reviews?.length || 0;
  if (n) {
    parts.push(`抓取到 ${n} 条评论，其中一条提到：${firstSentence(data.reviews[0], 80)}。`);
  } else {
    parts.push("本页未抓取到评论。");
  }

  const conflict = detectConflict(data.bullets || [], data.reviews || []);
  if (conflict) {
    parts.push(`提示：${conflict}，建议谨慎参考官方描述。`);
  }

  parts.push("以上为本地快速解读，接入后端后将给出更可靠的结论。");
  return parts.join(" ");
}

// 极简冲突检测（演示版，正式版应在后端做语义判断）
function detectConflict(bullets, reviews) {
  const off = bullets.join(" ").toLowerCase();
  const rev = reviews.join(" ").toLowerCase();
  const pairs = [
    [["warm", "保暖"], ["not warm", "thin", "偏薄", "不暖"], "官方称保暖，但评论提到偏薄或不够暖"],
    [["waterproof", "防水"], ["leak", "soaked", "not waterproof", "漏水", "渗水"], "官方称防水，但评论提到渗漏"],
    [["true to size", "标准尺码"], ["runs small", "too small", "偏小", "size up"], "官方称尺码标准，但评论提到偏小"],
    [["durable", "耐用"], ["fell apart", "poor quality", "易损", "质量差"], "官方称耐用，但评论提到质量问题"],
  ];
  for (const [offSig, revSig, label] of pairs) {
    if (offSig.some((s) => off.includes(s)) && revSig.some((s) => rev.includes(s))) {
      return label;
    }
  }
  return "";
}

function firstSentence(text, max) {
  if (!text) return "";
  const cut = text.split(/[。.!?！？]/)[0] || text;
  return cut.length > max ? cut.slice(0, max) + "…" : cut;
}
