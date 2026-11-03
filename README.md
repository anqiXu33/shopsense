# ShopSense: a voice accessibility layer for online stores

ShopSense is a **B2B product**: a layer that an e-commerce platform plugs into
its product pages so that blind and low-vision shoppers can shop by voice.
The retailer provides its catalogue and reviews; ShopSense indexes them and
answers in short, spoken, evidence-backed sentences.

The shopping assistants that platforms ship today are built for sighted
users: carousels of product cards, long chat answers, star graphics, "see
more" links. With a screen reader they are slow at best and unusable at
worst. Since 28 June 2025 the European Accessibility Act requires EU
e-commerce to meet WCAG 2.1 AA, so retailers need a fix that works on their
existing content rather than an overlay (see [strategy/](strategy/)).

This repository contains the engine and a **demo store** that stands in for
a retailer's site. The demo store runs on real Amazon shoe data.
(`extension/` is an earlier browser-extension prototype and is not
developed further.)

## The three features

| Feature | What the shopper does | What ShopSense does |
|---|---|---|
| **1. Spoken highlights** | Opens a product | Reads out the 3 points reviewers raise most, each with its count: *"Sizing: runs small (12 of 30 reviews mention this; 4 say it fits true to size)"* |
| **2. Ask the reviews** | Asks by voice: *"有没有人说偏窄？"* | Retrieves this product's reviews that relate to the question, answers only from them, says how many reviews back the answer, and says *"I don't know"* when none do |
| **3. Search by need** | Says a need: *"适合宽脚的跑鞋"* | Searches **all** reviews of **all** products in Qdrant, recommends the 5 best matches and says why, from the reviews |

The product page also reads out an **appearance description** written from
the product photo. Reviews say how a shoe fits and feels but rarely what it
looks like, and the photo is the one part of a listing a screen reader
cannot read.

Answers come in **Chinese or English** (switch in the header). Speech
output, speech recognition and the page language (`<html lang>`) follow
the switch.

### Why the numbers can be trusted

Every count a shopper hears is computed by code, never written by the model:

- **Highlights.** The model labels every review with stances from a fixed
  list (`runs_small`, `true_to_size`, `narrow`, `comfortable`, …) under a
  strict JSON schema, 10 reviews per call, so it cannot invent labels.
  Code counts the labels, picks the 3 most discussed aspects, and builds the
  sentence from bilingual templates. When another stance on the same aspect
  has at least 2 reviews, it is read out too.
- **Q&A.** The model marks each retrieved review true or false for "does
  this answer the question". The spoken count is the number marked true.
  When none is marked, the answer is a fixed "the reviews don't mention
  this" sentence, and the model's own text is discarded.
- **Search.** The ranking comes from Qdrant; the model only explains it,
  and is told to say so when the quoted reviews show a product does *not*
  fit.

Whether the reviews behind each count really say what is claimed is a
separate question; that is what the evaluation below measures.

### Why cross-product search needs vector retrieval

A shopper's need and the review that answers it rarely share words. A
shopper asks for *"shoes for wide feet"*; reviewers write *"roomy toe box"*,
*"I'm an EE"*, *"finally no pinching"*. The catalogue has no width field to
filter on, and keyword matching (BM25) only finds reviews that happen to
contain "wide" and "feet". BM25 also cannot match a Chinese query against
English reviews at all.

Embedding reviews and needs into the same vector space matches them by
meaning. Qdrant then does three things in one query: the similarity search
over 9,000 reviews, a payload filter (only 4–5 star reviews argue for a
recommendation), and a group-by on product, so the result is the 5 best
*products* rather than the 5 best reviews.

Two design choices came from testing:

- **Product name inside the review vector.** A review saying *"great grip
  on wet floors"* matches a kitchen-shoe need whether it is about a clog or
  a house slipper. Embedding `product name. review title. review text`
  lets the kind of shoe count too. In a side-by-side check this moved
  *"running shoes for wide feet"* from 2 to 5 running shoes in the top 5.
- **Chinese queries are translated first.** The reviews are English. With
  a small multilingual embedding model, *"防水的徒步靴"* (waterproof hiking
  boots) retrieved sneakers and water shoes; after a one-line LLM
  translation it retrieves hiking boots. English queries skip this step.

## Data

The catalogue is a subset of **Amazon Reviews 2023** (McAuley Lab, UCSD):

- Dataset: <https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023>,
  category `Clothing_Shoes_and_Jewelry`
- Paper: Hou, Li, He, Yan, Chen, McAuley. *Bridging Language and Items for
  Retrieval and Recommendation.* arXiv:2403.03952, 2024.
- **Used here for research and non-commercial demonstration only.** Product
  data, images and review texts belong to their original authors and
  Amazon; they are not covered by this repository's license.

**Subset.** 300 adult shoes (185 women's, 115 men's, 25+ sub-categories,
from sneakers to hiking boots and slippers). All have at least 1,000
ratings on Amazon, and each keeps 30 reviews of at least 80 characters:
9,000 reviews in all. Product images are linked from Amazon's CDN, not
copied.

**How it is built.** [scripts/build_dataset.py](scripts/build_dataset.py)
is deterministic and can be rerun. The two category files are 18 GB and
28 GB, and the review file is ordered by user, so the script fetches only a
fixed-size prefix of each with HTTP Range requests (600 MB of metadata,
1.5 GB of reviews). Popular products are spread evenly through the review
file, so the prefix already holds dozens of reviews for each of them.

## Architecture

```
Browser (React, Web Speech API)
   │  /api/products/{asin}?lang=   /api/ask   /api/search
   ▼
FastAPI  backend/main.py
   ├─ agent/review_insights.py   the three features
   ├─ agent/tools/review_search.py  Qdrant review search (filter, group-by)
   ├─ agent/tools/visual.py      Qdrant search over appearance descriptions
   ├─ core/llm.py                the only place that calls a language model
   └─ core/embeddings.py         multilingual-e5-small, local
Qdrant (embedded local mode, data/qdrant/)
   products · reviews · visual_semantic · knowledge
```

Offline steps, each resumable:

| Script | Output | Model calls |
|---|---|---|
| `scripts/build_dataset.py` | `data/shoes/products.json`, `reviews.json` | none |
| `scripts/build_highlights.py` | `data/shoes/highlights.json` | 3 per product |
| `scripts/generate_visual_descriptions.py` | `data/shoes/visual.json` | 1 per product (image) |
| `scripts/ingest_all.py` | Qdrant collections | none (local embeddings) |

| Component | Choice |
|---|---|
| Language model | `gpt-6-luna` (OpenAI), any OpenAI-compatible model via `.env` |
| Embeddings | `intfloat/multilingual-e5-small`, 384-dim, local |
| Vector DB | Qdrant, cosine, embedded local mode (or a server via `QDRANT_URL`) |
| Backend / Frontend | FastAPI · React + Vite |
| Speech | Browser Web Speech API (recognition and synthesis) |

### Switching models

Every model call goes through [core/llm.py](core/llm.py), which sends an
OpenAI-compatible `/chat/completions` request built from `.env`:

```
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-6-luna
LLM_EXTRA_BODY={"reasoning_effort": "low"}
```

Only parameters every provider understands are sent. Model-specific ones
go in `LLM_EXTRA_BODY`: GPT-6 models reject `temperature: 0`, while a local
Ollama model wants it. [.env.example](.env.example) has ready-made blocks
for DeepSeek and Ollama. The eval judge has its own optional `JUDGE_*`
settings, so the judge can stay fixed while the model under test changes.

**Why `gpt-6-luna`.** Prices are from OpenAI's pricing page, November 2026,
per 1M tokens:

| Model | Image input | Input | Output | Note |
|---|---|---|---|---|
| gpt-5-nano | yes | $0.05 | $0.40 | deprecated; OpenAI points to the Luna line instead |
| **gpt-6-luna** | yes | **$0.10** | **$0.50** | cheapest current model with image input |
| gpt-5.6-luna | yes | $0.20 | $1.20 | |
| gpt-5.4-mini | yes | $0.75 | $4.50 | |
| gpt-6.1-terra | yes | $1.00 | $5.00 | |

Strict JSON-schema output, image input and `reasoning_effort` were all
checked against the API before use.

**What the offline build cost** (gpt-6-luna, `reasoning_effort: low`):

| Step | Wall clock | Tokens in / out | Cost |
|---|---|---|---|
| Highlights, 300 products (900 calls, 8 in parallel) | 7 min | 1.55 M / 0.23 M | $0.27 |
| Appearance descriptions, 300 photos | 2 min | 0.10 M / 0.04 M | $0.03 |

## Accessibility (WCAG 2.1 AA)

Everything new can be done by keyboard alone and by voice alone.

| Action | Keyboard | Voice (after ⌥V / Alt+V) |
|---|---|---|
| Search by need | type in the search box, Enter | say the need |
| Open a result | Tab to its link, Enter | "打开第二款" / "open number two" |
| Hear highlights again | "Read highlights" button | "重复要点" / "repeat highlights" |
| Hear what it looks like | "Read appearance" button | "描述外观" / "what does it look like" |
| Ask the reviews | type the question, Enter | say the question |
| Stop speech | Esc | "停止" / "stop" |
| Back to the list | "Back" link | "返回" / "go back" |

- Focus moves to the product name when a page opens, and to the results
  heading after a search. Status changes are announced through `aria-live`
  regions, and answers through a `role="log"` region.
- **Auto-read** (header toggle) reads highlights and typed answers aloud
  with the built-in voice. Voice questions are always answered aloud.
  Screen-reader users can turn auto-read off so two voices never overlap;
  everything is still in the page for the screen reader.
- English product names and review quotes carry `lang="en"` inside the
  Chinese UI, so screen readers switch voice. Evidence quotes sit in
  `<details>` elements, closed by default.
- The light, dark and high-contrast themes are kept from the earlier
  version; new elements use the same colour tokens.

## Evaluation

All scripts and results are in [eval/](eval/).

### 1. Retrieval (cross-product search): Recall@5 and MRR

- **Queries.** [eval/queries.json](eval/queries.json) holds 30 shopper
  needs, each in English and Chinese (wide feet, standing all day,
  plantar fasciitis, kitchen work, …).
- **Systems compared**, all ranking products by their best-matching review:

  | System | Description |
  |---|---|
  | `bm25_en` | keyword BM25 over all reviews, English query (baseline) |
  | `vector_en_all` | Qdrant vector search over all reviews |
  | `vector_en` | the store's system: vector search over 4–5 star reviews |
  | `vector_zh` | the store's system with the Chinese query (translated, then searched) |

- **Pooling.** The top 5 of every system are pooled (337 query–product
  pairs, 11 per query on average) and **labelled by hand** in
  [eval/annotation/retrieval_labels.csv](eval/annotation/retrieval_labels.csv).
  Each row shows the product, its category and its 3 reviews closest to the
  need. The labelling rules are in
  [eval/annotation/README.md](eval/annotation/README.md).
- **Metrics.** [eval/retrieval_metrics.py](eval/retrieval_metrics.py)
  computes Recall@5 (relative to the pool, as in TREC) and MRR.

```
python eval/build_retrieval_pool.py   # done; rerunning overwrites the labels
# label the CSV
python eval/retrieval_metrics.py
```

**Results:** pending manual labelling.

### 2. Number check (highlights and Q&A)

[eval/check_numbers.py](eval/check_numbers.py) parses the numbers from the
text a shopper hears (Chinese and English) and compares them with the
reviews themselves. A judge model reads **each review on its own** and
answers yes or no: does this review make the claim, or answer the
question? The true count is the number of yes answers.

- Highlights: 30 products sampled with a fixed seed, every count spoken,
  including counter-views.
- Q&A: 15 other products × 2 questions from a fixed bank of 10, half asked
  in Chinese and half in English. The bank mixes answerable questions
  ("does it run small?") with ones reviews rarely cover ("is it
  waterproof?").

**Results** (generator and judge both `gpt-6-luna`; 5,475 judge calls,
16 min, $0.16; full per-claim detail in
[eval/results/number_check.json](eval/results/number_check.json)):

| | Highlights | Review Q&A |
|---|---|---|
| Spoken counts checked | 151 | 30 answers |
| Spoken total *N* correct ("of 30 reviews") | 100% | 100% |
| Spoken count **exactly** equals the true count | **32.5%** | **63.3%** |
| Off by at most 1 review | 70.9% | 90.0% |
| Off by at most 1 review or 20% | 76.8% | – |
| Mean absolute error (reviews) | 1.17 | 0.47 |
| Counted reviews the judge confirms (precision) | 86.2% | 55.3% |
| Confirmed reviews that were counted (recall) | 92.8% | 63.4% |
| "I don't know" answers that were right | – | 13 of 14 |

How to read it:

- **Highlights tend to over-count slightly** (mean spoken count 7.6
  against 7.1 true; 72 claims over, 30 under, 49 exact). Clear stances
  are reliable (`comfortable`: 92% precision, 97% recall; `runs_small`:
  87% and 100%). Subtle ones are not: `true_to_size` (58% precision),
  `looks_bad` (38%) and `supportive` (52%) get tagged on reviews that only
  hint at them. Raising the bar for those stances, or dropping them, is
  the obvious next step.
- **Q&A counts are mostly right, but not always for the right reviews.**
  The count is exact for 63% of answers and within one for 90%. Yet only
  55% of the reviews counted are confirmed by the judge, so some correct
  counts come from errors cancelling out. Some disagreements are the judge
  being stricter than a shopper would be (for "is it good for wide feet?",
  *"tighter than most shoes, got blisters"* was counted but not confirmed).
- **"I don't know" is reliable:** 13 of 14 were right. In the one miss
  ("is it waterproof?" for a boat shoe), the answering review says
  *"impervious to fresh and salt water"* and was not among the 10
  retrieved, a retrieval miss rather than a generation error.
- The Chinese and English highlights speak identical counts (checked on
  all 151).

### 3. Appearance descriptions (30 photos)

[eval/build_appearance_sheet.py](eval/build_appearance_sheet.py) samples 30
products with a fixed seed and exports their descriptions to
[eval/annotation/appearance_labels.csv](eval/annotation/appearance_labels.csv).
[eval/annotation/appearance_review.html](eval/annotation/appearance_review.html)
shows each photo next to its description. A person marks kind of shoe,
colour, upper, fastening and sole as right, wrong or not covered, and flags
invented details and Chinese–English mismatches.
[eval/appearance_metrics.py](eval/appearance_metrics.py) scores the sheet.

**Results:** pending manual labelling.

### Limitations

- **The judge is a language model, and here the same one.** Judging one
  review at a time is a different and simpler task than tagging 10 at once,
  but errors can still correlate. Set `JUDGE_*` to a different model for an
  independent check, or hand-label a sample of
  `eval/results/number_check.json`.
- **"Exact" is strict.** A count off by one review fails it, which is why
  `within_1` is reported too.
- **Q&A only sees the 10 retrieved reviews** out of 30. A review that
  answers the question but is not retrieved is not counted, which shows up
  as missed reviews and low recall.
- **Retrieval recall is relative to the pool.** A relevant shoe that no
  system retrieved is never labelled; 30 queries over 300 products is a
  small test set.
- **The Chinese query is translated by the model**, which does not run at
  temperature 0, so `vector_zh` rankings can vary slightly between runs.
- **Appearance descriptions come from one photo** and can be wrong about
  colour or material; the page says so.
- **The data is old and small:** 30 reviews per shoe, all from Amazon US,
  in English.

## Quick start

```bash
cp .env.example .env               # add LLM_API_KEY
pip install -r requirements.txt
cd frontend && npm install && cd ..

python scripts/build_dataset.py                  # ~2 GB download, cached in data/raw/
python scripts/build_highlights.py               # ~7 min, ~$0.27 with gpt-6-luna
python scripts/generate_visual_descriptions.py   # ~2 min, ~$0.03
python scripts/ingest_all.py                     # embeds locally, ~3 min

bash launch.sh                                   # http://127.0.0.1:5173
```

With `QDRANT_PATH` (embedded mode) only one process can open the database,
so stop the backend before running `scripts/` or `eval/`.

## Tests

```bash
python -m pytest tests/
```

The language model and Qdrant are stubbed, so no key or database is
needed. [tests/test_review_insights.py](tests/test_review_insights.py)
covers counting, rendering in both languages, "I don't know", query
translation, the eval parsers and the metrics.
[tests/test_agent.py](tests/test_agent.py) covers the earlier ReAct agent
and the extension endpoint.

## Project structure

```
shopsense/
├── agent/
│   ├── review_insights.py    # highlights, review Q&A, cross-product search
│   ├── tools/                # Qdrant search tools (reviews, visual, knowledge)
│   ├── react.py, legacy.py   # earlier ReAct agent (fabric-era /api/query)
│   └── page.py               # endpoint for the browser extension
├── backend/main.py           # FastAPI
├── core/                     # llm.py (model calls), embeddings.py
├── config/settings.py        # all configuration, from .env
├── data/shoes/               # the subset + highlights + appearance
├── eval/                     # queries, scripts, annotation sheet, results
├── frontend/                 # React store (i18n.js, voiceCommands.js, hooks/)
├── scripts/                  # dataset, highlights, descriptions, ingest
└── tests/
```

## License

Code: MIT. Data: see [Data](#data); research use only.
