/* ShopSense popup：读写设置到 chrome.storage.sync */

const fields = ["backendUrl", "height", "weight"];

// 载入已保存的设置
chrome.storage.sync.get(
  { backendUrl: "", height: "", weight: "" },
  (cfg) => {
    for (const k of fields) {
      const el = document.getElementById(k);
      if (el) el.value = cfg[k] ?? "";
    }
  }
);

// 保存
document.getElementById("save").addEventListener("click", () => {
  const out = {};
  for (const k of fields) {
    out[k] = document.getElementById(k).value.trim();
  }
  chrome.storage.sync.set(out, () => {
    const s = document.getElementById("saved");
    s.textContent = "已保存 ✓";
    setTimeout(() => (s.textContent = ""), 1500);
  });
});
