# ShopSense B2B 竞争格局与空位分析

> 目的:判断"把 ShopSense 做成 B2B 无障碍 PDP 内容引擎"在 2026 年的竞争空间里有没有可切入的缝。
> 结论先行:**"AI 生成 alt 文本"这一层已是红海,不能作为差异化;真正的空位在更上一层——可信、可感知的 PDP 体验层(富描述 + 评论综合 + 读屏问答),并明确对立于已被法律否定的 overlay 厂商。**

---

## 一、市场为什么现在存在(需求驱动)

- **欧洲无障碍法案(EAA)已于 2025-06-28 在 27 国生效**,要求电商达到 WCAG 2.1 AA(含"图片要有文字替代"),单次违规最高罚 10 万欧元;法国已在生效数周内对零售商发起法律函与紧急禁令。
- 过渡期到 2030-06-28,但**强制需求已经打开**,不需要再教育市场"为什么要做无障碍"。

这意味着:买方动机("why now")是现成的。竞争只在于"由谁、用什么形态来满足它"。

---

## 二、三类现有玩家

### 1) C 端 AI 购物助手 —— Be My Eyes / InnoSearch（不可正面竞争）

- Be My Eyes 是全球最大视障辅助 app,2025-05 接入 InnoSearch 的 AI 购物门户,覆盖 **50 万+ 零售商、10 亿+ 商品**,并已落地 Tesco、微软 Disability Answer Desk 等合作。
- **占据"帮盲人购物"的 C 端心智**。任何"给盲人用的独立购物 app/站点"都是它的主场,商品量与零售合作无法企及。
- **启示**:放弃 C 端;但它是 C 端 app,**不直接向零售商出售"商品页合规内容生成"**——这正是 B 端的留白。

### 2) 无障碍 Overlay 厂商 —— accessiBe / UserWay / EqualWeb（信誉崩塌,反成对立面）

- **FTC 于 2025-04 对 accessiBe 罚款 100 万美元**,指其对"自动达成 ADA 合规"做虚假/误导宣传。
- 2023–2024 间,装了 overlay 的 **800+ 商家照样被诉**,占数字无障碍诉讼的 25%+;研究显示 overlay **"遮盖而非修复"** 底层问题,甚至干扰读屏等辅助技术;700+ 无障碍专业人士联署反对。
- **启示**:市场已对"一行 JS 假装合规"反感。这是**定位机会**——"我们真正生成可用内容,不是遮盖";同时是**红线警告**——绝不能像 overlay 那样承诺"一键全合规",否则同样面临 FTC/诉讼风险。

### 3) Shopify "AI alt 文本"生成 app —— AltText.ai / Caseo / SmartAlt / ProductPilot / SEO HERO（已红海,差异化失效区）

- 多款应用已在 Shopify 应用商店,主打 **SEO + WCAG/ADA**,用视觉模型给商品图批量生成关键词丰富的 alt 字符串。
- 功能高度同质:单图 → 短 alt 串,以 SEO 排名为核心卖点。
- **启示**:**"生成 alt 文本"本身已是商品化能力,不能作为 ShopSense 的差异化**。但这些工具的产出止于"一句话 alt + SEO",**不做**:面向读屏用户的体验式富描述、跨源(图+评论+知识)综合、内容可信度校验、PDP 上的对话式问答。

---

## 三、能力对比矩阵

| 能力 | Be My Eyes/InnoSearch | Overlay(accessiBe等) | Shopify alt 文本 app | **ShopSense 定位** |
|---|---|---|---|---|
| 形态 | C 端 app | 网站注入 JS | 商户后台批处理 | 商户侧 PDP 内容引擎 |
| 买单方 | 个人用户/平台 | 网站主 | Shopify 商户 | 零售商合规+电商团队 |
| 图片→alt 短文本 | — | 声称(质量差) | ✅(核心) | ✅(基础项) |
| 体验式富描述(版型/质感/穿着场景) | 部分(实时) | ✗ | ✗ | ✅ **差异化** |
| 评论综合(读屏友好的"买家真实反馈") | ✗ | ✗ | ✗ | ✅ **差异化** |
| 内容可信度/冲突 QA(文案 vs 评论矛盾) | ✗ | ✗ | ✗ | ✅ **差异化** |
| PDP 上对话式问答 | app 内,非商户页 | ✗ | ✗ | ✅ **差异化** |
| 真正修复 vs 遮盖 | 修复(绕过原站) | **遮盖(已被 FTC 罚)** | 修复(有限) | 修复 |
| 合规审计报告 | ✗ | 营销噱头 | 部分 | ✅(销售敲门砖) |

---

## 四、空位（White Space）

把红海(alt 文本)和雷区(overlay)排除后,剩下的可防御空间是:

> **"可信、可感知的商品详情页体验层" —— 不止生成 alt 文本,而是把一件商品对读屏用户'讲清楚 + 讲可信':富外观描述 + 评论综合结论 + 内容矛盾预警 + 页面内问答。卖点是合规触发、SEO/转化持续兑现,并以'真正修复内容'对立于被罚的 overlay。**

支撑这个空位的三项现有资产(ShopSense 已有):
1. **多源综合**(图 + 评论 + 知识),而非单图 alt。
2. **冲突检测 → 重新包装为"内容可信度 QA"**:防止商品文案与真实评论矛盾,降低退货/法律风险——这对 B 端是 alt 文本工具给不了的价值。
3. **读屏优化的对话式问答**(结论先行、2–3 句、无干扰符号)。

---

## 五、诚实的风险与护城河评估

- **护城河薄**。AI 部分(调 VLM/LLM)是商品化的;alt 文本红海玩家完全可能向上扩展到"富描述 + 评论综合"。真正的壁垒只能来自:**合规可追溯(审计报告/认证背书)、平台集成深度(Shopify 等)、或分销与品牌信任**,而非算法本身。
- **合规承诺是红线**。FTC 已用 accessiBe 立威——文案必须是"协助达成 WCAG/降低风险",**绝不能写"保证全合规"**。
- **质量门槛高**。给零售商的描述若 AI 幻觉(编造卖点),是商户的法律与退货风险。**可信度 QA 不是加分项,是 B 端的入场券**。
- **平台自建风险**。Shopify/Salesforce 等可能把基础 alt 文本能力内建,进一步压缩低端;更需往"体验层 + 合规审计"上走。

---

## 六、给 ShopSense 的切入建议(一句话)

不要做"又一个 alt 文本工具",也不要碰"overlay";**做"对立于 overlay 的、真正可用的 PDP 无障碍体验层"**,以 EAA 合规为楔子进场,以 SEO/转化/省成本维持付费,以"内容可信度 QA"建立差异和入场资格。

---

### 来源
- European Commission — European Accessibility Act (EAA): https://commission.europa.eu/strategy-and-policy/policies/justice-and-fundamental-rights/disability/european-accessibility-act-eaa_en
- Bird & Bird — Guide to navigating the EAA for online retailers: https://www.twobirds.com/en/insights/2025/a-guide-to-navigating-the-european-accessibility-act-for-online-retailers-service-providers-and-plat
- Accessible.org — EAA Ecommerce Services Requirements: https://accessible.org/eaa-ecommerce-services-requirements/
- Be My Eyes — In-App Accessible Shopping with InnoSearch AI: https://www.bemyeyes.com/news/be-my-eyes-to-provide-in-app-accessible-shopping/
- Be My Eyes — Tesco partnership: https://www.bemyeyes.com/business/news/be-my-eyes-partners-with-tesco/
- TestParty — Why 800+ Businesses with AccessiBe Were Still Sued: https://testparty.ai/blog/why-800-businesses-with-accessibe-were-still-sued
- Law Office of Lainey Feingold — UserWay Overlay Lawsuit (2025): https://www.lflegal.com/2025/02/userway-overlay-lawsuit/
- AltText.ai — Shopify / Ecommerce AI alt text: https://alttext.ai/solutions/shopify
- Caseo.ai — AI Alt Text & SEO for Shopify: https://caseo.ai/
