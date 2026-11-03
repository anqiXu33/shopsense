/* ShopSense content script
 * 职责：在亚马逊商品页上 ①抓取页面内容 ②叠加一个无障碍按钮 ③语音播报解读
 * 设计原则：叠加而不接管——只新增一个可聚焦控件和一个 ARIA live 区，绝不改写页面本身的无障碍结构。
 */

(() => {
  "use strict";

  // 只在"看起来像商品页"时激活（亚马逊商品页都有 #productTitle）
  const titleEl = document.querySelector("#productTitle");
  if (!titleEl) return;

  let lastTrigger = 0; // 防抖：命令 + 键盘 + 点击可能重复触发
  let speaking = false;

  // ── ① 抓取页面内容 ───────────────────────────────────────────────
  function grabProduct() {
    const text = (sel) => document.querySelector(sel)?.innerText?.trim() || "";

    const bullets = [...document.querySelectorAll("#feature-bullets li")]
      .map((li) => li.innerText.trim())
      .filter(Boolean)
      .slice(0, 6);

    const reviews = [...document.querySelectorAll("[data-hook='review-body']")]
      .map((el) => el.innerText.trim())
      .filter(Boolean)
      .slice(0, 8);

    const imageUrl =
      document.querySelector("#landingImage")?.src ||
      document.querySelector("#imgTagWrapperId img")?.src ||
      "";

    return {
      asin: (location.pathname.match(/\/dp\/([A-Z0-9]{10})/) || [])[1] || "",
      title: text("#productTitle"),
      brand: text("#bylineInfo"),
      price: text("#corePrice_feature_div .a-offscreen") || text(".a-price .a-offscreen"),
      bullets,
      description: bullets.join("。 "),
      reviews,
      imageUrl,
      url: location.href,
    };
  }

  // ── ② 无障碍 UI：浮动按钮 + 状态播报区 ────────────────────────────
  const liveRegion = document.createElement("div");
  liveRegion.setAttribute("aria-live", "polite");
  liveRegion.setAttribute("aria-atomic", "true");
  liveRegion.className = "shopsense-sr-only";
  document.body.appendChild(liveRegion);

  const btn = document.createElement("button");
  btn.id = "shopsense-fab";
  btn.type = "button";
  btn.textContent = "🔊 ShopSense";
  btn.setAttribute("aria-label", "用语音解读这件商品（快捷键 Alt+V）");
  document.body.appendChild(btn);
  btn.addEventListener("click", activate);

  function setStatus(msg) {
    liveRegion.textContent = msg;
  }

  // ── 语音播报（兼容读屏：仅在用户主动触发时朗读）────────────────────
  function speak(textToSpeak) {
    if (!("speechSynthesis" in window)) {
      setStatus("当前浏览器不支持语音合成。");
      return;
    }
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(textToSpeak);
    // 中文内容用中文嗓音，否则英文
    u.lang = /[一-鿿]/.test(textToSpeak) ? "zh-CN" : "en-US";
    u.rate = 1.0;
    u.onstart = () => {
      speaking = true;
      btn.textContent = "⏹ 停止";
    };
    u.onend = () => {
      speaking = false;
      btn.textContent = "🔊 ShopSense";
    };
    speechSynthesis.speak(u);
  }

  function stopSpeaking() {
    speechSynthesis.cancel();
    speaking = false;
    btn.textContent = "🔊 ShopSense";
  }

  // ── ③ 主流程：抓取 → 交后台处理 → 播报 ───────────────────────────
  function activate() {
    const now = Date.now();
    if (now - lastTrigger < 800) return; // 防抖
    lastTrigger = now;

    if (speaking) {
      stopSpeaking();
      return;
    }

    const data = grabProduct();
    if (!data.title) {
      setStatus("没有在本页找到商品信息。");
      return;
    }

    setStatus("正在解读，请稍候。");
    speak("正在解读，请稍候。");

    chrome.runtime.sendMessage({ type: "ASK", data }, (res) => {
      if (chrome.runtime.lastError || !res) {
        const msg = "解读失败，请确认插件后台正常。";
        setStatus(msg);
        speak(msg);
        return;
      }
      setStatus(res.answer);
      speak(res.answer);
    });
  }

  // 快捷键（来自 manifest commands 的转发）
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg && msg.type === "ACTIVATE") activate();
  });

  // 页内键盘兜底：Alt+V（避开在输入框里打字的情况）
  document.addEventListener("keydown", (e) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "");
    if (e.altKey && (e.key === "v" || e.key === "V") && !typing) {
      e.preventDefault();
      activate();
    }
  });

  console.log("[ShopSense] content script ready on", location.href);
})();
