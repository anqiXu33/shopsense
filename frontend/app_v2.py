"""
frontend/app_v2.py

Updated Gradio UI for ShopSense with new Qdrant-first agent.
Features:
  - Product selector with ASIN
  - LLM-driven tool selection display
  - Tool execution transparency panel
  - Dynamic context visualization
  - Answer generation with TTS

Run:
    python frontend/app_v2.py
"""

import json
import sys
import os
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr

# Load new agent components
from agent.tool_selector import select_tools
from agent.executor import execute_tools
from agent.context_assembler import assemble_context, ContextAssembler
from agent.conflict_detector import detect_conflicts, format_conflicts
from agent.tools import list_tools, get_all_schemas
from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, TEXT_MODEL

# Load product data
with open("data/sample_products.json") as f:
    PRODUCTS = json.load(f)

PRODUCT_MAP = {p["name"]: p for p in PRODUCTS}
PRODUCT_NAMES = list(PRODUCT_MAP.keys())


def generate_llm_answer(context: str, user_query: str) -> str:
    """Generate answer using LLM API."""
    try:
        response = requests.post(
            f"{DASHSCOPE_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": TEXT_MODEL,
                "messages": [
                    {"role": "system", "content": context},
                    {"role": "user", "content": user_query}
                ],
                "temperature": 0.7,
                "max_tokens": 500,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error generating answer: {str(e)}"


def format_tool_calls(tool_calls):
    """Format tool calls for display."""
    if not tool_calls:
        return "No tools selected."
    
    lines = []
    for i, tc in enumerate(tool_calls, 1):
        name = tc.get("name", "unknown")
        args = tc.get("arguments", {})
        args_str = ", ".join([f"{k}={v}" for k, v in args.items() if v])
        lines.append(f"{i}. **{name}**({args_str})")
    
    return "\n".join(lines)


def format_tool_results(results):
    """Format tool execution results for display."""
    if not results:
        return "No results."
    
    lines = []
    for tool_name, result in results.items():
        if result.success:
            icon = "✅"
            score = f"score:{result.relevance_score:.3f}"
            time_ms = f"{result.execution_time_ms:.1f}ms" if result.execution_time_ms else "N/A"
            
            # Get result summary
            data_keys = list(result.data.keys()) if result.data else []
            summary = f"keys={data_keys}" if data_keys else "empty"
            
            lines.append(f"{icon} **{tool_name}** | {score} | {time_ms} | {summary}")
        else:
            icon = "❌"
            error = result.error_message[:50] if result.error_message else "Unknown error"
            lines.append(f"{icon} **{tool_name}** | Error: {error}")
    
    return "\n".join(lines)


def format_context_preview(context, max_chars=500):
    """Format context for preview display."""
    if len(context) > max_chars:
        return context[:max_chars] + "...\n\n[truncated]"
    return context


def process_query(product_name, user_query):
    """
    Process user query through the new agent pipeline.
    
    Returns:
        (answer, tool_selection, tool_results, context_preview, conflicts)
    """
    if not product_name or not user_query.strip():
        return (
            "Please select a product and enter a question.",
            "No product selected.",
            "No tools executed.",
            "No context generated.",
            "No conflicts detected."
        )
    
    product = PRODUCT_MAP[product_name]
    current_asin = product.get("id", "")
    
    try:
        # Step 1: Tool Selection
        reasoning, tool_calls = select_tools(
            user_query=user_query,
            current_asin=current_asin
        )
        
        tool_selection_md = f"""### Reasoning
{reasoning}

### Selected Tools
{format_tool_calls(tool_calls)}
"""
        
        # Step 2: Execute Tools
        if tool_calls:
            tool_results = execute_tools(tool_calls)
            tool_results_md = format_tool_results(tool_results)
        else:
            tool_results = {}
            tool_results_md = "No tools were selected for execution."
        
        # Step 3: Conflict Detection
        conflicts = detect_conflicts(tool_results)
        conflicts_md = format_conflicts(conflicts) if conflicts else "No conflicts detected between knowledge and reviews."
        
        # Step 4: Context Assembly
        product_info = {
            "asin": product.get("id", ""),
            "name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "price": product.get("price", 0),
            "rating": product.get("rating", 4.0),
        }
        
        context = assemble_context(
            user_query=user_query,
            current_asin=current_asin,
            product_info=product_info,
            tool_results=tool_results
        )
        
        context_preview_md = format_context_preview(context)
        
        # Step 5: Generate Answer (using the context with LLM)
        answer = generate_llm_answer(context, user_query)
        
        return (
            answer,
            tool_selection_md,
            tool_results_md,
            context_preview_md,
            conflicts_md
        )
        
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n\n{traceback.format_exc()}"
        return (
            f"Error processing query: {str(e)}",
            "Error in tool selection.",
            "No tools executed due to error.",
            "No context generated.",
            "No conflicts detected."
        )


# Gradio UI
css = """
.answer-box textarea { 
    font-size: 16px !important; 
    line-height: 1.7 !important; 
}

/* All transparency panels - Markdown components */
.tool-selection, .tool-results, .conflicts {
    font-size: 15px !important;
    line-height: 1.6 !important;
    border: 2px solid;
    border-radius: 8px;
    padding: 20px;
    color: #000000 !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    min-height: 200px;
}

.tool-selection {
    background: #e3f2fd !important;
    border-color: #2196f3 !important;
}

.tool-results {
    background: #f3e5f5 !important;
    border-color: #9c27b0 !important;
}

.conflicts {
    background: #ffebee !important;
    border-color: #f44336 !important;
}

/* Ensure all text in panels is black */
.tool-selection p, .tool-selection span, .tool-selection div,
.tool-results p, .tool-results span, .tool-results div,
.conflicts p, .conflicts span, .conflicts div {
    color: #000000 !important;
}

/* Context Assembly - Textbox */
.context-preview {
    background: #fff8c5 !important;
    border: 2px solid #f9a825 !important;
    border-radius: 8px;
}

.context-preview textarea,
.context-preview .wrap,
.context-preview input,
.context-preview .input {
    font-size: 14px !important;
    line-height: 1.5 !important;
    background: #fff8c5 !important;
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
}

.context-preview * {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
}

/* Panel headers */
.tool-selection h4, .tool-results h4, .conflicts h4 {
    font-size: 16px !important;
    font-weight: 600 !important;
    margin-bottom: 12px !important;
    color: #000000 !important;
}

/* Code blocks within panels */
.tool-selection code, .tool-results code, .conflicts code {
    font-size: 13px !important;
    background: rgba(255,255,255,0.7);
    padding: 2px 6px;
    border-radius: 4px;
    color: #000000 !important;
}

/* Strong/bold text */
.tool-selection strong, .tool-results strong, .conflicts strong,
.tool-selection b, .tool-results b, .conflicts b {
    color: #000000 !important;
    font-weight: 700 !important;
}
"""

with gr.Blocks(
    title="ShopSense v2 — Qdrant-First Agent",
    theme=gr.themes.Soft(),
    css=css
) as demo:
    
    gr.Markdown("""
    # 🛍️ ShopSense v2
    ### Qdrant-First Agent with LLM Tool Selection
    *Powered by Agentic RAG + Qdrant | Dynamic Tool Selection + Context Engineering*
    ---
    """)
    
    with gr.Row():
        # Left column - Input
        with gr.Column(scale=2):
            gr.Markdown("### 📝 Input")
            
            product_selector = gr.Dropdown(
                choices=PRODUCT_NAMES,
                label="Select a Product",
                value=PRODUCT_NAMES[0] if PRODUCT_NAMES else None,
            )
            
            query_input = gr.Textbox(
                label="Your Question",
                placeholder="e.g., Is this warm enough for -10°C? I'm 170cm with sensitive skin.",
                lines=3,
            )
            
            gr.Markdown("**Example questions:**")
            gr.Examples(
                examples=[
                    [PRODUCT_NAMES[0], "这件保暖吗？我170cm敏感肌"],
                    [PRODUCT_NAMES[0], "What color is this? Describe the appearance."],
                    [PRODUCT_NAMES[1], "Is this waterproof? Can I wear it in rain?"],
                    [PRODUCT_NAMES[2], "What size should I get? I'm 165cm 60kg."],
                    [PRODUCT_NAMES[3], "Is cashmere itchy for sensitive skin?"],
                ],
                inputs=[product_selector, query_input],
            )
            
            submit_btn = gr.Button("🔍 Ask ShopSense", variant="primary", size="lg")
        
        # Right column - Output
        with gr.Column(scale=3):
            gr.Markdown("### 💬 Answer")
            
            answer_output = gr.Textbox(
                label="",
                lines=8,
                elem_classes=["answer-box"],
                interactive=False,
            )
            
            with gr.Row():
                tts_btn = gr.Button("🔊 Read Aloud", size="sm")
                clear_btn = gr.Button("🗑️ Clear", size="sm")
    
    # Transparency Panel
    gr.Markdown("---")
    gr.Markdown("### 🔬 Agent Transparency Panel")
    gr.Markdown("*See how the agent works: tool selection → execution → context assembly*")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("#### 1️⃣ Tool Selection")
            tool_selection_output = gr.Markdown(
                label="Selected Tools",
                elem_classes=["transparency-panel", "tool-selection"]
            )
        
        with gr.Column():
            gr.Markdown("#### 2️⃣ Tool Execution Results")
            tool_results_output = gr.Markdown(
                label="Execution Results",
                elem_classes=["transparency-panel", "tool-results"]
            )
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("#### 3️⃣ Context Assembly")
            context_output = gr.Textbox(
                label="Generated Context (sent to LLM)",
                lines=10,
                elem_classes=["context-preview"],
                interactive=False,
            )
        
        with gr.Column():
            gr.Markdown("#### 4️⃣ Conflict Detection")
            conflicts_output = gr.Markdown(
                label="Detected Conflicts",
                elem_classes=["transparency-panel", "conflicts"]
            )
    
    # Event handlers
    submit_btn.click(
        fn=process_query,
        inputs=[product_selector, query_input],
        outputs=[
            answer_output,
            tool_selection_output,
            tool_results_output,
            context_output,
            conflicts_output
        ],
    )
    
    query_input.submit(
        fn=process_query,
        inputs=[product_selector, query_input],
        outputs=[
            answer_output,
            tool_selection_output,
            tool_results_output,
            context_output,
            conflicts_output
        ],
    )
    
    # TTS handler
    tts_btn.click(
        fn=None,
        js="""
        () => {
            const answer = document.querySelector('.answer-box textarea')?.value;
            if (answer) {
                const utterance = new SpeechSynthesisUtterance(answer);
                utterance.rate = 0.9;
                window.speechSynthesis.speak(utterance);
            }
        }
        """,
    )
    
    # Clear handler
    clear_btn.click(
        fn=lambda: ("", "", "", "", ""),
        outputs=[
            answer_output,
            tool_selection_output,
            tool_results_output,
            context_output,
            conflicts_output
        ],
    )
    
    # Available tools section
    gr.Markdown("---")
    gr.Markdown("### 🛠️ Available Tools")
    
    tools_md = "\n".join([f"- **{t}**" for t in list_tools()])
    gr.Markdown(f"The agent can automatically select from these {len(list_tools())} tools:\n{tools_md}")


if __name__ == "__main__":
    import socket
    
    # Get local IP address
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("=" * 60)
    print("🛍️  ShopSense v2 - Qdrant-First Agent")
    print("=" * 60)
    print(f"\n📱 Access URLs:")
    print(f"   Local:   http://127.0.0.1:7860")
    print(f"   LAN:     http://{local_ip}:7860")
    print(f"\n👤 Hostname: {hostname}")
    print("=" * 60)
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
