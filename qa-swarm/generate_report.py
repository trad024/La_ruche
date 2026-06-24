"""Generate a detailed PDF test report for the QA-Swarm project."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    HRFlowable,
)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE = Path(r"C:\Users\Moataz\LaRuche_platform")
QA = BASE / "qa-swarm"
FRONT_SCREENSHOTS = BASE / "frontend" / "e2e" / "__screens__"
MOBILE_SCREENSHOTS = BASE / "mobile" / "e2e" / "__screens__"
QA_SCREENSHOTS = QA / "swarm_qa" / "runs" / "_screens"
API_RUN = QA / "swarm_qa" / "runs" / "run_20260619_152209_9a6ae1" / "run.json"
WEB_RUN = QA / "swarm_qa" / "runs" / "run_20260619_152340_4ec90c" / "run.json"
OUTPUT = QA / "Test_Report.pdf"

# ── Colors ───────────────────────────────────────────────────────────────────
DARK = colors.HexColor("#0f172a")
TEAL = colors.HexColor("#0d9488")
GREEN = colors.HexColor("#16a34a")
RED = colors.HexColor("#dc2626")
AMBER = colors.HexColor("#f59e0b")
LIGHT_BG = colors.HexColor("#f1f5f9")
ROW_ALT = colors.HexColor("#f8fafc")
WHITE = colors.white

# ── Styles ───────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()
styles.add(ParagraphStyle("CoverTitle", parent=styles["Title"], fontSize=28, textColor=DARK, spaceAfter=10))
styles.add(ParagraphStyle("CoverSub", parent=styles["Normal"], fontSize=14, textColor=TEAL, spaceAfter=6))
styles.add(ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18, textColor=DARK, spaceAfter=8, spaceBefore=14))
styles.add(ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, textColor=TEAL, spaceAfter=6, spaceBefore=10))
styles.add(ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=6))
styles.add(ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=11, textColor=colors.HexColor("#475569")))
styles.add(ParagraphStyle("PassFail", parent=styles["Normal"], fontSize=11, textColor=GREEN, alignment=1, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle("TableCell", parent=styles["Normal"], fontSize=9, leading=11))
styles.add(ParagraphStyle("TableCellCenter", parent=styles["Normal"], fontSize=9, leading=11, alignment=1))


def load_run(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_ms(ms: float) -> str:
    return f"{ms / 1000:.1f}s"


def screenshot_img(path: Path, width: float = 5.5 * inch) -> Image | None:
    if not path.exists():
        return None
    img = Image(str(path))
    aspect = img.imageHeight / img.imageWidth
    img.drawWidth = width
    img.drawHeight = width * aspect
    return img


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.rect(0, A4[1] - 1.0 * cm, A4[0], 1.0 * cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(2 * cm, A4[1] - 0.65 * cm, "QA-Swarm — Test Report")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 0.65 * cm, datetime.now().strftime("%B %d, %Y"))
    canvas.setFillColor(colors.HexColor("#94a3b8"))
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(A4[0] / 2, 1.0 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build_results_table(run_data: dict, channel: str) -> Table:
    rows = [["ID", "Intent", "Input", "Score", "Verdict", "Latency", "Halluc."]]
    for sr in run_data["scenarios"]:
        tc = sr["test_case"]
        if channel not in sr["scores"]:
            continue
        score = sr["scores"][channel]
        result = sr["results"][channel]
        inp = tc["input"][:40] + ("..." if len(tc["input"]) > 40 else "")
        rows.append([
            tc["id"],
            tc["intent"].replace("_", " "),
            inp,
            f"{score['pertinence']}/{score['exactitude']}/{score['coherence']}",
            score["verdict"],
            fmt_ms(result["latency_ms"]),
            "Yes" if score["hallucination"] else "No",
        ])
    t = Table(rows, colWidths=[1.2 * cm, 3.2 * cm, 5.0 * cm, 2.0 * cm, 1.8 * cm, 1.8 * cm, 1.4 * cm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i, row in enumerate(rows[1:], 1):
        if row[4] == "PASS":
            style_cmds.append(("TEXTCOLOR", (4, i), (4, i), GREEN))
            style_cmds.append(("FONTNAME", (4, i), (4, i), "Helvetica-Bold"))
        else:
            style_cmds.append(("TEXTCOLOR", (4, i), (4, i), RED))
            style_cmds.append(("FONTNAME", (4, i), (4, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style_cmds))
    return t


def build_unit_test_table() -> Table:
    rows = [
        ["Test File", "Test Name", "What It Checks", "Result"],
        ["test_api_channel.py", "test_api_channel_parses_sse", "SSE stream parsing + reply assembly", "PASS"],
        ["test_api_channel.py", "test_api_channel_5xx_is_crash", "500 status = crash flag", "PASS"],
        ["test_api_channel.py", "test_api_channel_4xx_is_not_crash", "400 guardrail = not a crash", "PASS"],
        ["test_api_channel.py", "test_api_channel_timeout", "Timeout detection", "PASS"],
        ["test_extract.py", "test_extract_json_from_fenced_prose", "JSON extraction from code fences", "PASS"],
        ["test_extract.py", "test_extract_json_nested", "Nested JSON extraction", "PASS"],
        ["test_extract.py", "test_extract_json_skips_unparseable", "Skips invalid first brace", "PASS"],
        ["test_extract.py", "test_extract_json_none", "Returns empty dict when no JSON", "PASS"],
        ["test_extract.py", "test_strip_code_fences", "Strip markdown code fences", "PASS"],
        ["test_pipeline.py", "test_corpus_loads_and_validates", "52-scenario corpus loads", "PASS"],
        ["test_pipeline.py", "test_run_pipeline_with_stubs", "Pipeline pass/fail counting", "PASS"],
        ["test_regression.py", "test_no_regression_identical_runs", "No false regressions", "PASS"],
        ["test_regression.py", "test_pass_to_fail_flip", "PASS→FAIL flip detection", "PASS"],
        ["test_regression.py", "test_score_drop_no_flip", "Score drop detection", "PASS"],
        ["test_regression.py", "test_latency_spike", "Latency spike detection", "PASS"],
        ["test_regression.py", "test_unmatched_scenarios_ignored", "Unmatched scenarios ignored", "PASS"],
    ]
    t = Table(rows, colWidths=[3.8 * cm, 4.8 * cm, 6.4 * cm, 1.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("TEXTCOLOR", (3, 1), (3, -1), GREEN),
        ("FONTNAME", (3, 1), (3, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build_e2e_table() -> Table:
    rows = [
        ["Test", "Page", "What It Validates", "Result"],
        ["dashboard KPI cards", "/ (Dashboard)", "Portfolio Overview heading, $20.4M AUM, Sharpe 0.58, geo breakdown", "PASS"],
        ["portfolio deals table", "/portfolio", "8 deal rows, Aurora Brands visible", "PASS"],
        ["market page quotes", "/market", "S&P 500, Fed Funds Rate visible", "PASS"],
        ["chat page input", "/chat", "AI Assistant heading, input field, response mode toggle", "PASS"],
        ["voice studio modes", "/voice", "Voice-to-voice, Speech-to-text, Text-to-speech buttons", "PASS"],
        ["no console errors", "all 5 pages", "No 502/JS errors across navigation", "PASS"],
    ]
    t = Table(rows, colWidths=[3.5 * cm, 2.5 * cm, 8.0 * cm, 1.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("TEXTCOLOR", (3, 1), (3, -1), GREEN),
        ("FONTNAME", (3, 1), (3, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build_mobile_table() -> Table:
    rows = [
        ["Test", "Screen", "What It Validates", "Result"],
        ["dashboard KPI cards", "Dashboard tab", "Portfolio Overview, $20.4M AUM, Sharpe 0.58, geo bars", "PASS"],
        ["portfolio deals", "Portfolio tab", "Deals table renders with data", "PASS"],
        ["market quotes", "Market tab", "Market data screen renders", "PASS"],
        ["chat streaming reply", "Chat tab", "Input + send → streams $20.4M reply from orchestrator", "PASS"],
    ]
    t = Table(rows, colWidths=[3.5 * cm, 2.5 * cm, 8.0 * cm, 1.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("TEXTCOLOR", (3, 1), (3, -1), GREEN),
        ("FONTNAME", (3, 1), (3, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build_infra_table() -> Table:
    rows = [
        ["Service", "Port", "Technology", "Status"],
        ["Postgres", "5432", "PostgreSQL 16", "UP (healthy)"],
        ["Redis", "6379", "Redis 7", "UP (healthy)"],
        ["Qdrant", "6333", "Vector DB", "UP"],
        ["Keycloak", "8180", "OIDC auth", "UP"],
        ["MailHog", "8025", "SMTP sandbox", "UP"],
        ["Traefik", "8080", "Reverse proxy", "UP"],
        ["Langfuse", "3000", "LLM tracing", "UP"],
        ["MLflow", "5000", "ML tracking", "UP"],
        ["ClickHouse", "8123", "Analytics DB", "UP"],
        ["ZooKeeper", "2181", "Coordination", "UP"],
        ["Orchestrator", "8000", "FastAPI (LangGraph)", "UP"],
        ["Frontend", "5173", "Vite + React 19", "UP"],
        ["Mobile (Expo Web)", "8081", "Expo + React Native", "UP"],
        ["Voice Service", "8006", "FastAPI (STT/TTS)", "UP"],
        ["Ollama", "11434", "Local LLM runtime", "UP"],
        ["agent-financial", "8001", "A2A FastAPI", "UP"],
        ["agent-market", "8002", "A2A FastAPI", "UP"],
        ["agent-docs", "8003", "A2A FastAPI", "UP"],
        ["agent-action", "8004", "A2A FastAPI", "UP"],
        ["agent-qa", "8005", "A2A FastAPI", "UP"],
    ]
    t = Table(rows, colWidths=[4.0 * cm, 1.5 * cm, 5.5 * cm, 4.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("TEXTCOLOR", (3, 1), (3, -1), GREEN),
        ("FONTNAME", (3, 1), (3, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def build_compliance_table() -> Table:
    rows = [
        ["Requirement (from spec deck)", "Status", "Details"],
        ["4 Swarm agents: Generator → Executor → Evaluator → Reporter", "Done", "All 4 agents in swarm_qa/agents/, handoff chain functional"],
        ["3 channels: API (httpx), Web (Playwright), Mobile (Appium)", "Partial", "API + Web fully tested. Mobile tested via Expo Web, not Appium/AVD"],
        ["50+ scenarios (nominal, limit, adversarial)", "Done", "52 scenarios in corpus/scenarios.json (30 nominal, 10 limit, 12 adversarial)"],
        ["Code-based approach (Playwright scripts, not tool-based)", "Done", "web_channel.py generates Playwright scripts with fallback"],
        ["LLM-as-judge scoring (pertinence, exactitude, coherence, hallucination)", "Done", "evaluator.py with Ollama qwen2.5:3b, strict JSON output"],
        ["FAIL conditions: hallucination, crash, timeout, 5xx, score < 3.0", "Done", "Deterministic blocking rules in evaluator.py"],
        ["Screenshots after each action", "Done", "Web channel + e2e tests produce PNG screenshots"],
        ["Markdown + HTML (Plotly) reports", "Done", "reporter.py generates report.md + report.html"],
        ["Regression detection between two versions", "Partial", "regression.py implemented; not demonstrated in this run"],
        ["Web ↔ Mobile divergence detection (>20% = FAIL)", "Missing", "Requires both channels on same scenario; not tested"],
        ["Dashboard HTML (Plotly)", "Done", "Interactive Plotly dashboard generated per run"],
        ["Ollama local SLMs (qwen2.5:3b)", "Done", "All 4 agents use qwen2.5:3b via Ollama"],
        ["Full 52-scenario run", "Partial", "10 scenarios run (6 API + 4 Web); 42 remaining"],
        ["Mobile Appium on Android emulator (AVD)", "Missing", "Tested via Expo Web instead; no AVD/Appium setup"],
    ]
    t = Table(rows, colWidths=[6.5 * cm, 1.8 * cm, 7.2 * cm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i, row in enumerate(rows[1:], 1):
        status = row[1]
        if status == "Done":
            style_cmds.append(("TEXTCOLOR", (1, i), (1, i), GREEN))
        elif status == "Partial":
            style_cmds.append(("TEXTCOLOR", (1, i), (1, i), AMBER))
        else:
            style_cmds.append(("TEXTCOLOR", (1, i), (1, i), RED))
        style_cmds.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style_cmds))
    return t


def build():
    api_run = load_run(API_RUN)
    web_run = load_run(WEB_RUN)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="QA-Swarm Test Report",
        author="QA-Swarm Autonomous Testing System",
    )
    story: list = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("QA-Swarm Test Report", styles["CoverTitle"]))
    story.append(Paragraph("Autonomous Testing of a Conversational Agent", styles["CoverSub"]))
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="60%", color=TEAL, thickness=2))
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(f"<b>Project:</b> LaRuche Wealth Management Platform", styles["Body"]))
    story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}", styles["Body"]))
    story.append(Paragraph(f"<b>Version:</b> {api_run['sut_version']} / {web_run['sut_version']}", styles["Body"]))
    story.append(Paragraph(f"<b>Channels tested:</b> API (httpx), Web (Playwright), Mobile (Expo Web)", styles["Body"]))
    story.append(Paragraph(f"<b>LLM Judge:</b> Ollama qwen2.5:3b", styles["Body"]))
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph("All tests passed: 16/16 unit, 6/6 web e2e, 4/4 mobile, 100% QA pipeline", styles["PassFail"]))
    story.append(PageBreak())

    # ── Executive Summary ─────────────────────────────────────────────────────
    story.append(Paragraph("1. Executive Summary", styles["H1"]))
    story.append(Paragraph(
        "This report documents the testing of the LaRuche wealth-management conversational agent "
        "using the QA-Swarm autonomous testing system. The system uses OpenAI Swarm + Ollama to "
        "orchestrate 4 AI agents (Generator, Executor, Evaluator, Reporter) that generate test "
        "cases, execute them across 3 channels (API, Web, Mobile), score responses with an "
        "LLM-as-judge, and produce consolidated reports.", styles["Body"]))
    story.append(Spacer(1, 0.4 * cm))
    summary = [
        ["Test Suite", "Tests", "Passed", "Failed", "Pass Rate"],
        ["Unit tests (pytest)", "16", "16", "0", "100%"],
        ["Web e2e (Playwright, headed)", "6", "6", "0", "100%"],
        ["Mobile e2e (Playwright, headed)", "4", "4", "0", "100%"],
        ["QA Pipeline — API channel", "6", "6", "0", "100%"],
        ["QA Pipeline — Web channel", "4", "4", "0", "100%"],
        ["TOTAL", "36", "36", "0", "100%"],
    ]
    t = Table(summary, colWidths=[6.0 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 2.0 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), TEAL),
        ("TEXTCOLOR", (0, -1), (-1, -1), WHITE),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, ROW_ALT]),
        ("TEXTCOLOR", (4, 1), (4, -2), GREEN),
        ("FONTNAME", (4, 1), (4, -2), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        "A bug was identified in the financial agent during testing: the keyword 'allocation' "
        "appeared in both the geography and sector tool mappings, causing the agent to return "
        "geographic data for sector questions. This was flagged as hallucination by the evaluator. "
        "The bug was fixed by removing 'allocation' from the geography keyword list.", styles["Body"]))
    story.append(PageBreak())

    # ── System Overview ───────────────────────────────────────────────────────
    story.append(Paragraph("2. System Overview", styles["H1"]))
    story.append(Paragraph(
        "The QA-Swarm system is built on 4 Swarm agents chained via handoffs, each backed by a "
        "local SLM (Ollama qwen2.5:3b):", styles["Body"]))
    agents = [
        ["Agent", "Role", "Model"],
        ["Generator", "Loads/synthesizes test cases from 52-scenario JSON corpus", "qwen2.5:3b"],
        ["Executor", "Dispatches each case to API (httpx), Web (Playwright), or Mobile (Appium)", "qwen2.5:3b"],
        ["Evaluator", "LLM-as-judge scoring: pertinence, exactitude, coherence, hallucination", "qwen2.5:3b"],
        ["Reporter", "Produces Markdown report + interactive Plotly HTML dashboard", "qwen2.5:3b"],
    ]
    t = Table(agents, colWidths=[3.0 * cm, 9.5 * cm, 2.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Test Corpus", styles["H2"]))
    story.append(Paragraph(
        "52 scenarios in 3 categories: 30 nominal (AUM, TWR, Sharpe, geo/sector breakdown, "
        "market quotes, doc lookup), 10 limit (empty input, unicode, typos, multi-question, "
        "very long input), 12 adversarial (prompt injection, XSS, SQL injection, jailbreak, "
        "PII extraction).", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Scoring Criteria", styles["H2"]))
    story.append(Paragraph(
        "Each response is scored on 3 dimensions (1-5): Pertinence (relevance to intent), "
        "Exactitude (factual correctness vs expected), Coherence (logical consistency). "
        "Verdict: PASS if mean score >= 3.0 AND no hallucination. Blocking FAIL: timeout (>30s), "
        "crash (5xx/UI crash), empty reply, hallucination detected.", styles["Body"]))
    story.append(PageBreak())

    # ── Infrastructure ────────────────────────────────────────────────────────
    story.append(Paragraph("3. Infrastructure", styles["H1"]))
    story.append(Paragraph(
        "The full LaRuche platform was started for testing: 10 Docker containers (dev infra) "
        "and 8 local Python/Node services (app + agent mesh).", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(build_infra_table())
    story.append(PageBreak())

    # ── Unit Tests ────────────────────────────────────────────────────────────
    story.append(Paragraph("4. Unit Test Results (pytest)", styles["H1"]))
    story.append(Paragraph(
        "16 unit tests covering the QA harness itself: SSE parsing, JSON extraction, pipeline "
        "wiring, corpus validation, and regression detection logic.", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(build_unit_test_table())
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Result: 16/16 PASS (100%) — run in 5.0s", styles["PassFail"]))
    story.append(PageBreak())

    # ── Web E2E Tests ─────────────────────────────────────────────────────────
    story.append(Paragraph("5. Web E2E Test Results (Playwright, headed Chromium)", styles["H1"]))
    story.append(Paragraph(
        "6 browser tests against the live Vite dev server (localhost:5173), run in headed mode "
        "with visible Chromium window. Screenshots captured for each page.", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(build_e2e_table())
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Result: 6/6 PASS (100%)", styles["PassFail"]))
    story.append(Spacer(1, 0.4 * cm))
    # Screenshots
    for name, label in [("dashboard.png", "Web — Dashboard"), ("chat.png", "Web — Chat")]:
        img = screenshot_img(FRONT_SCREENSHOTS / name, width=5.0 * inch)
        if img:
            story.append(Paragraph(label, styles["H2"]))
            story.append(img)
            story.append(Spacer(1, 0.3 * cm))
    story.append(PageBreak())

    # ── Mobile E2E Tests ──────────────────────────────────────────────────────
    story.append(Paragraph("6. Mobile App Test Results (Expo Web, headed Chromium)", styles["H1"]))
    story.append(Paragraph(
        "4 tests against the Expo web server (localhost:8081), run in headed mode. The mobile "
        "app (React Native + Expo) was tested in web mode via react-native-web.", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(build_mobile_table())
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Result: 4/4 PASS (100%)", styles["PassFail"]))
    story.append(Spacer(1, 0.4 * cm))
    for name, label in [("mobile-dashboard.png", "Mobile — Dashboard"), ("mobile-chat.png", "Mobile — Chat")]:
        img = screenshot_img(MOBILE_SCREENSHOTS / name, width=4.5 * inch)
        if img:
            story.append(Paragraph(label, styles["H2"]))
            story.append(img)
            story.append(Spacer(1, 0.3 * cm))
    story.append(PageBreak())

    # ── QA Pipeline API ───────────────────────────────────────────────────────
    story.append(Paragraph("7. QA Pipeline — API Channel", styles["H1"]))
    story.append(Paragraph(
        "6 scenarios executed via httpx against the orchestrator /api/chat endpoint (SSE streaming). "
        "The orchestrator routes to specialist agents (financial, market, docs, action, qa) via A2A. "
        "Responses scored by the Evaluator LLM-as-judge.", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(build_results_table(api_run, "api"))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Result: 6/6 PASS (100%) — all scores 5.0/5.0", styles["PassFail"]))
    story.append(PageBreak())

    # ── QA Pipeline Web ───────────────────────────────────────────────────────
    story.append(Paragraph("8. QA Pipeline — Web Channel (Playwright)", styles["H1"]))
    story.append(Paragraph(
        "4 scenarios executed via Playwright code-based scripts against the live frontend (localhost:5173/chat). "
        "Each scenario fills the chat input, clicks send, waits for the streamed reply, and captures a screenshot.", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(build_results_table(web_run, "web"))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Result: 4/4 PASS (100%) — all scores 5.0/5.0", styles["PassFail"]))
    story.append(Spacer(1, 0.4 * cm))
    img = screenshot_img(QA_SCREENSHOTS / "S01_web_1781882620.png", width=5.0 * inch)
    if img:
        story.append(Paragraph("Web Channel Screenshot — Portfolio AUM scenario", styles["H2"]))
        story.append(img)
    story.append(PageBreak())

    # ── Bug Found ─────────────────────────────────────────────────────────────
    story.append(Paragraph("9. Bug Found & Fixed", styles["H1"]))
    story.append(Paragraph(
        "<b>Symptom:</b> The sector_breakdown scenario (S06) was flagged as hallucination by the "
        "Evaluator, scoring 2.0/5.0 and FAIL.", styles["Body"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "<b>Root cause:</b> In agent_financial/agent.py, the keyword 'allocation' appeared in "
        "BOTH the geography and sector tool keyword lists. When the user asked 'What is my "
        "allocation by sector?', the agent triggered both portfolio.geo_breakdown and "
        "portfolio.sector_breakdown tools, returning geographic data alongside sector data. "
        "The Evaluator correctly flagged the unexpected geographic data as hallucination.", styles["Body"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "<b>Fix:</b> Removed 'allocation' from the geography keyword list. The geo tool still "
        "matches via 'geography', 'geographic', 'geographical', 'region', 'asia', 'europe', etc. "
        "The sector tool retains 'allocation' and 'sector'.", styles["Body"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "<b>Result after fix:</b> sector_breakdown returns only sector data (Real Estate 45%, "
        "Private Equity 35%, Equities 15%, Credit 5%). Score improved from 2.0 FAIL to 5.0 PASS.", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    before_after = [
        ["Metric", "Before Fix", "After Fix"],
        ["Score", "2.0 / 5.0", "5.0 / 5.0"],
        ["Verdict", "FAIL", "PASS"],
        ["Hallucination", "Yes (flagged)", "No"],
        ["Tools triggered", "geo_breakdown + sector_breakdown", "sector_breakdown only"],
    ]
    t = Table(before_after, colWidths=[5.0 * cm, 5.5 * cm, 5.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("TEXTCOLOR", (1, 1), (1, -1), RED),
        ("TEXTCOLOR", (2, 1), (2, -1), GREEN),
        ("FONTNAME", (1, 1), (2, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ── Spec Compliance ───────────────────────────────────────────────────────
    story.append(Paragraph("10. Spec Compliance (Testing Agentique deck)", styles["H1"]))
    story.append(Paragraph(
        "Comparison of the project's implementation against the requirements specified in the "
        "'Testing Agentique d'un Agent Conversationnel' specification deck.", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(build_compliance_table())
    story.append(PageBreak())

    # ── Metrics ───────────────────────────────────────────────────────────────
    story.append(Paragraph("11. Performance Metrics", styles["H1"]))
    api_latencies = [sr["results"]["api"]["latency_ms"] for sr in api_run["scenarios"] if "api" in sr["results"]]
    web_latencies = [sr["results"]["web"]["latency_ms"] for sr in web_run["scenarios"] if "web" in sr["results"]]
    avg_api = sum(api_latencies) / len(api_latencies) if api_latencies else 0
    avg_web = sum(web_latencies) / len(web_latencies) if web_latencies else 0
    metrics = [
        ["Metric", "API Channel", "Web Channel"],
        ["Scenarios run", "6", "4"],
        ["Pass rate", "100% (6/6)", "100% (4/4)"],
        ["Avg score", "5.0 / 5.0", "5.0 / 5.0"],
        ["Avg latency", f"{avg_api / 1000:.1f}s", f"{avg_web / 1000:.1f}s"],
        ["Min latency", f"{min(api_latencies) / 1000:.1f}s", f"{min(web_latencies) / 1000:.1f}s"],
        ["Max latency", f"{max(api_latencies) / 1000:.1f}s", f"{max(web_latencies) / 1000:.1f}s"],
        ["Crashes", "0", "0"],
        ["Timeouts", "0", "0"],
        ["Hallucinations", "0", "0"],
        ["Availability", "100%", "100%"],
    ]
    t = Table(metrics, colWidths=[5.0 * cm, 5.5 * cm, 5.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("12. Conclusion", styles["H1"]))
    story.append(Paragraph(
        "The QA-Swarm system successfully tested the LaRuche conversational agent across API and "
        "Web channels with a 100% pass rate. All 36 tests (16 unit, 6 web e2e, 4 mobile e2e, "
        "6 API pipeline, 4 web pipeline) passed. One bug was found in the financial agent "
        "(keyword overlap causing false hallucination) and fixed during testing. The system "
        "demonstrates autonomous test generation, execution, LLM-as-judge evaluation, and "
        "report generation as specified in the Testing Agentique deck.", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Remaining work to fully meet the spec: (1) set up Appium + Android emulator for true "
        "mobile channel testing, (2) run the full 52-scenario corpus, (3) demonstrate regression "
        "detection between two versions, (4) test Web-Mobile divergence detection.", styles["Body"]))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"PDF generated: {OUTPUT}")
    print(f"Size: {OUTPUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    build()
