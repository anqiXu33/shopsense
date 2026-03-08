"""
frontend/app.py
Gradio UI for ShopSense demo.

Features:
  - Product selector (dropdown)
  - Text input + voice input (via browser)
  - Agent transparency panel (tool call trace)
  - Answer display + TTS button

Run:
    python frontend/app.py
"""

import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
from agent.agent import run

# ── Load product data ─────────────────────────────────────────────────────────
with open("data/sample_products.json") as f:
    PRODUCTS = json.load(f)

PRODUCT_MAP = {p["name"]: p for p in PRODUCTS}
PRODUCT_NAMES = list(PRODUCT_MAP.keys())

# ── Core handler ──────────────────────────────────────────────────────────────
def handle_query(product_name: str, user_query: str):
    if not product_name or not user_query.strip():
        return "Please select a product and enter a question.", "", ""

    product = PRODUCT_MAP[product_name]

    result = run(user_query=user_query, product=product)

    # Format trace for display
    trace_lines = []
    for step in result["trace"]:
        status_icon = "✅" if step["status"] == "success" else "❌"
        count = f"→ {step.get('result_count', '?')} results" if step["status"] == "success" else f"→ {step.get('error', '')}"
        trace_lines.append(f"{status_icon} **{step['tool']}** {count}")

    trace_md = "\n".join(trace_lines) if trace_lines else "No tool calls recorded."

    intent_md = (
        f"**Detected intent:** `{result['intent']['primary_intent']}`\n\n"
        f"**Entities:** {result['intent']['entities']}"
    )

    return result["answer"], trace_md, intent_md


# ── Gradio UI ─────────────────────────────────────────────────────────────────
with gr.Blocks(
    title="ShopSense — Accessible Shopping Assistant",
    theme=gr.themes.Soft(),
    css="""
        .answer-box textarea { font-size: 16px !important; line-height: 1.7 !important; }
        .trace-box { font-size: 13px; background: #f8f9fa; }
    """
) as demo:

    gr.Markdown("""
    # 🛍️ ShopSense
    ### Accessible Shopping Assistant for Visually Impaired Users
    *Powered by Agentic RAG + Qdrant | Hackathon Demo*
    ---
    """)

    with gr.Row():
        with gr.Column(scale=2):
            product_selector = gr.Dropdown(
                choices=PRODUCT_NAMES,
                label="Select a Product",
                value=PRODUCT_NAMES[0] if PRODUCT_NAMES else None,
            )

            query_input = gr.Textbox(
                label="Your Question",
                placeholder="e.g. Is this warm enough for -10°C? I'm 170cm 55kg.",
                lines=3,
            )

            mic_btn = gr.Button("🎤 Speak Your Question", size="sm")
            mic_btn.click(
                fn=None,
                js="""
                () => {
                    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                    if (!SpeechRecognition) {
                        alert("Speech recognition is not supported in this browser. Try Chrome.");
                        return [];
                    }
                    const recognition = new SpeechRecognition();
                    recognition.lang = "en-US";
                    recognition.interimResults = false;
                    recognition.onresult = (event) => {
                        const transcript = event.results[0][0].transcript;
                        const textarea = document.querySelector("#query_input textarea");
                        if (textarea) {
                            textarea.value = transcript;
                            textarea.dispatchEvent(new Event("input", { bubbles: true }));
                        }
                    };
                    recognition.onerror = (event) => {
                        console.error("Speech recognition error:", event.error);
                    };
                    recognition.start();
                    return [];
                }
                """,
                inputs=[],
                outputs=[],
            )

            gr.Markdown("**Example questions:**")
            examples = gr.Examples(
                examples=[
                    [PRODUCT_NAMES[0], "What color is this? Can you describe how it looks?"],
                    [PRODUCT_NAMES[0], "Is this warm enough for -10 degrees?"],
                    [PRODUCT_NAMES[1], "I have sensitive skin, is this fabric safe for me?"],
                    [PRODUCT_NAMES[2], "I'm 170cm, which size should I get?"],
                    [PRODUCT_NAMES[1], "What are the main complaints from buyers?"],
                ],
                inputs=[product_selector, query_input],
            )

            submit_btn = gr.Button("🔍 Ask ShopSense", variant="primary", size="lg")

        with gr.Column(scale=3):
            answer_output = gr.Textbox(
                label="ShopSense Answer",
                lines=6,
                elem_classes=["answer-box"],
                interactive=False,
            )

            tts_btn = gr.Button("🔊 Read Answer Aloud", size="sm")
            tts_btn.click(
                fn=None,
                js="""
                (answer) => {
                    if (answer) {
                        const utterance = new SpeechSynthesisUtterance(answer);
                        utterance.rate = 0.9;
                        window.speechSynthesis.speak(utterance);
                    }
                }
                """,
                inputs=[answer_output],
            )

            gr.Markdown("---")
            gr.Markdown("### 🔬 Agent Transparency Panel")
            gr.Markdown("*Shows how the agent built its answer — the Context Engineering process*")

            intent_output = gr.Markdown(label="Detected Intent")
            trace_output = gr.Markdown(label="Tool Call Trace", elem_classes=["trace-box"])

    submit_btn.click(
        fn=handle_query,
        inputs=[product_selector, query_input],
        outputs=[answer_output, trace_output, intent_output],
    )
    query_input.submit(
        fn=handle_query,
        inputs=[product_selector, query_input],
        outputs=[answer_output, trace_output, intent_output],
    )


if __name__ == "__main__":
    demo.launch(share=True)  # share=True creates a public URL for demo
