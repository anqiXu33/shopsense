# 视障用户网购真实痛点 — 二手研究发现

> 目的:用真实用户的原话和已发表研究,检验"视障网购"到底是真需求还是"为了做而做",并判断 ShopSense 的三个候选差异化"缝"哪个真、哪个假。
> 方法:检索 + 抓取 视障社区(AppleVis)、无障碍行业博客、以及 3 篇做了视障用户访谈/观察的学术论文(CHI/ASSETS/arXiv)。这是**二手研究**,不能替代你亲自访谈,但足以判断方向真伪、并让访谈问得更准。

---

## 一句话结论

**问题空间是真的,而且被反复证实;但 ShopSense 原来的具体功能(官方文案 vs 评论的"冲突检测")并不是用户喊得最响的痛点。** 喊得最响的是:拿不到能信的基本信息(颜色/版型/材质)、无法核验 AI 说得对不对、以及因此**被迫依赖明眼人**。讽刺的是——ShopSense 自己的标语"从依赖他人描述,到独立做决定"恰好命中了这个真痛点,只是功能没全瞄准它。

---

## 一、被反复证实的真实痛点(附原话)

**1. 商品图没有有意义的描述 —— 最基础的墙。**
> "Most retailers rely on images... and often provide no alternative or alt-tag descriptions."(多数零售商靠图片呈现,且常常没有任何替代文字)

**2. 颜色命名让人崩溃。**
> 用户原话:"finding information about the product is difficult because they have these weird names for colors"(颜色名怪得让人没法判断),例如 `black-150` 这种数字命名。

**3. 关键决策信息(尺码/材质/版型/搭配)缺失且不可及。** 服装类尤其严重——拿不到 fit、material、pattern、outfit coordination 这些信息。

**4. 决策疲劳 → 依赖他人,这是情感上最痛的一条。**
> "Many blind users resort to sending their top choices to friends or family for their opinions because they don't have the time—or energy—to wade through endless options, reviews, and return policies."(很多盲人干脆把心仪的几件发给亲友拿主意,因为没精力翻完无尽的选项、评论和退货政策)
> 一篇 2024 论文的标题直接是:**"We are at the mercy of others' opinion"**(我们受制于他人的意见)。

**5. 结账/购物车环节也碎裂。** 读屏不播报已选的尺码/颜色,"移除"按钮对应错商品,导致误删。

**6. 后果量化:约 2/3 的电商交互被盲人用户中途放弃**(因不可及)。

---

## 二、现有 AI 工具(Be My Eyes / Seeing AI)的局限 —— 这是"缝"所在

这一节最关键,因为它说明**为什么"已经有 Be My Eyes 了"不等于问题已解决**。来自 ASSETS 2024 论文《Misfitting With AI: How Blind People Verify and Contest AI Errors》的访谈:

**1. AI 会出错,而盲人几乎无法独立核验 —— 信任的根本裂缝。**
> P3:"we know some of this is wrong"(我们知道这些里有些是错的);并反驳"AI 替你看"的前提——"seeing is... interpreting"。
> 另一用户:"Artificial intelligence can be wrong, and a blind person like me would have little way of noticing unless I knew in advance what was in an image."(AI 会错,而像我这样的盲人除非事先就知道图里是什么,否则几乎察觉不到)

**2. 因为不敢信,只在"低风险"场景用。**
> P7:"I mostly use [AI VAT] in low-risk situations."
> **购买决策不是低风险场景** —— 这正是现有工具不被信任、覆盖不到的地方。

**3. 不能追问、是一次性的。**
> "you cannot really ask [Seeing AI] a question because you take your picture and you get the description and that's it."(没法追问,拍一张、给一段描述,就结束了)
> Be My AI 被吐槽"生成长度太短、会被截断"。

**4. 颜色/商品识别实际会错**:把薰衣草紫衬衫说成浅蓝、把一盒玉米说成"可能是冰棍或雪糕"。

---

## 三、三个候选"缝"的真伪判定

| 候选缝 | 判定 | 依据 |
|---|---|---|
| **① 可信 / 信息可被信任**(你最在乎的) | **真,但要重新定义** | 最响的不是"拆穿卖家文案",而是"我无法核验 AI/描述是否属实,只能在低风险时用"。痛点是**信任**,不是**揭露**。把"冲突检测"升级为"可核验、带出处、敢用于决策的信息",才打在真痛点上。 |
| **② 在真实网站上可用**(非封闭门户) | **真,但偏 B 端** | 2/3 弃单、结账碎裂、导航失效都说明真实站点是坏的;但"修好零售商的站"本质是 B 端的活,绕回前面的 B 端机会。C 端要做,只能靠浏览器插件在别人站上叠加,技术和维护成本高。 |
| **③ 个性化决策支持**(不止描述,帮我决定) | **真,且可能最强** | "发给亲友拿主意""没精力翻评论和退货政策""受制于他人意见"——这些都是**决策**之痛,不是**描述**之痛。现有工具止于"描述一张图",没人做"基于你的身材/需求,替你把评论和选项综合成一个能独立做的决定"。 |

---

## 四、对"是不是为了做而做"的回答

- **需求本身:不是编的。** 学术界(CHI/ASSETS 多篇访谈研究)和社区(AppleVis 等)反复记录,且有量化后果(2/3 弃单)。
- **原来的功能瞄准:有点偏。** "官方 vs 评论的冲突检测"是个聪明的点,但不是用户喊得最响的;它是"揭露式"的,而用户要的是"我能不能信、能不能不靠别人决定"。
- **最该瞄准的真痛点:独立决策。** 即 ShopSense 标语本身——把"受制于他人意见"变成"自己就能做的、可信的购买决定"。这条线同时吸收了你最在乎的"可信"(信息要敢信)和最强的"决策支持"。

**所以:方向真,初版瞄歪;改瞄准点,它可以是真有用的。**

---

## 五、由此给 C 端"真有用版"的瞄准建议

不要做"又一个图片描述器"(Be My Eyes 已占,且只解决描述、不解决信任和决策)。要做的是:

> **一个让视障用户能"独立、可信地完成购买决策"的助手:不只描述商品,而是把图、评论、规格综合成"对你而言"的判断,且每条结论可溯源、敢用于真实购买——把"受制于他人意见"变成"我自己就能定"。**

你的 agent(综合 + 可信 + 能对话)在这个定位下全部用得上,而且正好补现有工具的三个洞:能追问(对话)、有出处可信(可信)、面向决策而非描述(综合)。

---

## 六、下一步(仍然不可跳过)

二手研究只能证明"方向不假、瞄准要改"。**它不能替代你亲自验证"独立决策"这个新瞄准点是否真的让用户眼睛一亮。** 建议拿本文件里的痛点当访谈提纲,去 r/Blind、AppleVis、本地盲协、UZH disability services 找 8–10 人,只问一句开口:"你上一次网购最抓狂的瞬间是什么?",看是否有人自发提到"被迫依赖别人/不敢信描述"。有共鸣 → 真有用;没有 → 诚实承认并再调整。

---

### 来源
- UsableNet — How I shop online as a blind person:https://blog.usablenet.com/how-i-shop-online-as-a-blind-person
- UsableNet — A Blind Person's Perspective on Mobile Accessibility in Ecommerce:https://blog.usablenet.com/a-blind-persons-perspective-on-mobile-accessibility-in-ecommerce
- ACM CHI 2023 — The Barriers to Online Clothing Websites for Visually Impaired People:https://dl.acm.org/doi/fullHtml/10.1145/3563657.3595978
- MDPI 2025 — Beyond Accessibility Compliance: Information on Apparel Shopping Websites for the Blind:https://www.mdpi.com/2075-4698/15/4/90
- AudioEye — What It's Like to Shop Online When You're Blind:https://www.audioeye.com/post/what-its-like-to-shop-online-when-youre-blind/
- ASSETS 2024 — Misfitting With AI: How Blind People Verify and Contest AI Errors:https://arxiv.org/html/2408.06546v1
- arXiv 2024 — "We are at the mercy of others' opinion": Supporting Blind People in Recreational Window Shopping:https://arxiv.org/pdf/2405.06611
- AFB AccessWorld 2025 — Product Review: InnoSearch:https://afb.org/aw/summer2025/innosearch-review
