from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "MedRAG_Project_Report.pdf"

NAVY = colors.HexColor("#102A43")
BLUE = colors.HexColor("#2563EB")
CYAN = colors.HexColor("#0EA5E9")
MINT = colors.HexColor("#10B981")
PALE_BLUE = colors.HexColor("#EAF2FF")
PALE_MINT = colors.HexColor("#EAFBF5")
PALE_AMBER = colors.HexColor("#FFF7E6")
INK = colors.HexColor("#243B53")
MUTED = colors.HexColor("#627D98")
LINE = colors.HexColor("#D9E2EC")
WHITE = colors.white


def _register_fonts() -> tuple[str, str]:
    candidates = [
        (
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
    ]
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("MedRAGSans", regular))
            pdfmetrics.registerFont(TTFont("MedRAGSans-Bold", bold))
            return "MedRAGSans", "MedRAGSans-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = _register_fonts()


def para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


class ArchitectureDiagram(Flowable):
    def __init__(self, width: float, height: float = 115 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def _box(self, canvas, x, y, w, h, title, subtitle, fill, stroke=LINE):
        canvas.setFillColor(fill)
        canvas.setStrokeColor(stroke)
        canvas.setLineWidth(0.8)
        canvas.roundRect(x, y, w, h, 7, fill=1, stroke=1)
        canvas.setFillColor(NAVY)
        canvas.setFont(FONT_BOLD, 8.5)
        canvas.drawCentredString(x + w / 2, y + h - 13, title)
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT, 6.7)
        for idx, line in enumerate(subtitle.split("\n")):
            canvas.drawCentredString(x + w / 2, y + h - 26 - idx * 9, line)

    def _arrow(self, canvas, x1, y1, x2, y2, label=None):
        canvas.setStrokeColor(CYAN)
        canvas.setFillColor(CYAN)
        canvas.setLineWidth(1.35)
        canvas.line(x1, y1, x2, y2)
        import math

        angle = math.atan2(y2 - y1, x2 - x1)
        size = 5
        points = [
            (x2, y2),
            (x2 - size * math.cos(angle - 0.55), y2 - size * math.sin(angle - 0.55)),
            (x2 - size * math.cos(angle + 0.55), y2 - size * math.sin(angle + 0.55)),
        ]
        path = canvas.beginPath()
        path.moveTo(*points[0])
        path.lineTo(*points[1])
        path.lineTo(*points[2])
        path.close()
        canvas.drawPath(path, fill=1, stroke=0)
        if label:
            canvas.setFont(FONT, 6.2)
            canvas.setFillColor(MUTED)
            canvas.drawCentredString((x1 + x2) / 2, (y1 + y2) / 2 + 4, label)

    def draw(self):
        c = self.canv
        w = self.width
        c.setFillColor(colors.HexColor("#F8FAFC"))
        c.roundRect(0, 0, w, self.height, 10, fill=1, stroke=0)

        margin = 12
        gap = 10
        box_w = (w - 2 * margin - 3 * gap) / 4
        y_top = self.height - 54
        h = 42
        xs = [margin + i * (box_w + gap) for i in range(4)]
        self._box(c, xs[0], y_top, box_w, h, "Sources", "Guideline PDFs\nPubMed abstracts", PALE_BLUE)
        self._box(c, xs[1], y_top, box_w, h, "Parse + enrich", "LlamaParse\nclinical metadata", PALE_MINT)
        self._box(c, xs[2], y_top, box_w, h, "Embed + index", "FastEmbed\nQdrant collection", PALE_BLUE)
        self._box(c, xs[3], y_top, box_w, h, "Evidence store", "chunks + source\nmetadata", PALE_MINT)
        for i in range(3):
            self._arrow(c, xs[i] + box_w, y_top + h / 2, xs[i + 1], y_top + h / 2)

        c.setFillColor(MUTED)
        c.setFont(FONT_BOLD, 7)
        c.drawString(margin, y_top + h + 8, "INDEXING PATH")

        y_bottom = 48
        self._box(c, xs[0], y_bottom, box_w, h, "User", "Streamlit UI\nor API client", PALE_BLUE)
        self._box(c, xs[1], y_bottom, box_w, h, "Input safety", "prompt-injection\nclassification", PALE_AMBER)
        self._box(c, xs[2], y_bottom, box_w, h, "RAG service", "retrieve evidence\ngenerate answer", PALE_MINT)
        self._box(c, xs[3], y_bottom, box_w, h, "Output safety", "clinical policy\ncheck + response", PALE_AMBER)
        for i in range(3):
            self._arrow(c, xs[i] + box_w, y_bottom + h / 2, xs[i + 1], y_bottom + h / 2)
        c.setFillColor(MUTED)
        c.setFont(FONT_BOLD, 7)
        c.drawString(margin, y_bottom + h + 8, "QUERY PATH")

        evidence_x = xs[3] + box_w / 2
        c.setStrokeColor(colors.HexColor("#94A3B8"))
        c.setDash(3, 2)
        c.line(evidence_x, y_top, evidence_x, y_bottom + h + 7)
        c.setDash()
        c.setFillColor(MUTED)
        c.setFont(FONT, 6.2)
        c.drawRightString(evidence_x - 4, (y_top + y_bottom + h) / 2, "retrieval")

        c.setFillColor(NAVY)
        c.setFont(FONT_BOLD, 9)
        c.drawString(margin, 17, "Shared interfaces")
        c.setFillColor(MUTED)
        c.setFont(FONT, 7.4)
        c.drawString(margin + 82, 17, "CLI  |  FastAPI  |  Streamlit  ->  one RAGService")


class ProductMockup(Flowable):
    def __init__(self, width: float, height: float = 96 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(colors.HexColor("#F1F5F9"))
        c.setStrokeColor(LINE)
        c.roundRect(0, 0, w, h, 9, fill=1, stroke=1)
        sidebar = 88
        c.setFillColor(NAVY)
        c.roundRect(0, 0, sidebar, h, 9, fill=1, stroke=0)
        c.rect(sidebar - 9, 0, 9, h, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 13)
        c.drawString(13, h - 26, "MedRAG")
        c.setFont(FONT, 7)
        c.setFillColor(colors.HexColor("#BFDBFE"))
        c.drawString(13, h - 39, "Clinical evidence assistant")
        for idx, label in enumerate(("Ask", "Sources", "Evaluations", "Guardrails")):
            y = h - 68 - idx * 28
            if idx == 0:
                c.setFillColor(colors.HexColor("#1D4ED8"))
                c.roundRect(9, y - 8, sidebar - 18, 22, 5, fill=1, stroke=0)
            c.setFillColor(WHITE if idx == 0 else colors.HexColor("#CBD5E1"))
            c.setFont(FONT_BOLD if idx == 0 else FONT, 7.5)
            c.drawString(18, y, label)

        x = sidebar + 18
        content_w = w - x - 18
        c.setFillColor(NAVY)
        c.setFont(FONT_BOLD, 13)
        c.drawString(x, h - 28, "Ask a clinical guideline question")
        c.setFillColor(MUTED)
        c.setFont(FONT, 7.2)
        c.drawString(x, h - 42, "Answers are grounded in indexed evidence and are educational only.")

        c.setFillColor(WHITE)
        c.setStrokeColor(LINE)
        c.roundRect(x, h - 78, content_w, 24, 5, fill=1, stroke=1)
        c.setFillColor(INK)
        c.setFont(FONT, 7.5)
        c.drawString(x + 9, h - 69, "What do guidelines say about first-line therapy for hypertension?")
        c.setFillColor(BLUE)
        c.roundRect(x + content_w - 47, h - 74, 39, 16, 4, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 7)
        c.drawCentredString(x + content_w - 27.5, h - 68, "ASK")

        card_y = h - 184
        c.setFillColor(WHITE)
        c.setStrokeColor(LINE)
        c.roundRect(x, card_y, content_w, 90, 7, fill=1, stroke=1)
        c.setFillColor(MINT)
        c.circle(x + 13, card_y + 75, 4, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont(FONT_BOLD, 9)
        c.drawString(x + 23, card_y + 71, "Evidence-grounded answer")
        answer = [
            "Guidelines generally recommend lifestyle changes and selected first-line",
            "antihypertensive classes, individualized by comorbidities and clinical context.",
            "A qualified clinician should interpret targets and treatment choices.",
        ]
        c.setFillColor(INK)
        c.setFont(FONT, 7.3)
        for i, line in enumerate(answer):
            c.drawString(x + 13, card_y + 54 - i * 11, line)
        c.setFillColor(PALE_MINT)
        c.roundRect(x + 13, card_y + 10, 70, 16, 4, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#047857"))
        c.setFont(FONT_BOLD, 6.8)
        c.drawCentredString(x + 48, card_y + 16, "CONFIDENCE 0.84")

        source_y = 11
        c.setFillColor(WHITE)
        c.setStrokeColor(LINE)
        c.roundRect(x, source_y, content_w, 62, 7, fill=1, stroke=1)
        c.setFillColor(NAVY)
        c.setFont(FONT_BOLD, 8.5)
        c.drawString(x + 13, source_y + 51, "Evidence and sources")
        rows = [
            ("WHO_BP.pdf", "guideline", "cardiology"),
            ("PubMed abstract", "research_abstract", "cardiology"),
        ]
        for i, row in enumerate(rows):
            y = source_y + 33 - i * 16
            c.setFillColor(INK)
            c.setFont(FONT, 7)
            c.drawString(x + 13, y, row[0])
            c.setFillColor(MUTED)
            c.drawRightString(x + content_w - 13, y, f"{row[1]}  |  {row[2]}")


def build_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            fontName=FONT_BOLD,
            fontSize=29,
            leading=33,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            fontName=FONT,
            fontSize=13,
            leading=18,
            textColor=MUTED,
            spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "H1",
            fontName=FONT_BOLD,
            fontSize=20,
            leading=24,
            textColor=NAVY,
            spaceBefore=2,
            spaceAfter=11,
        ),
        "h2": ParagraphStyle(
            "H2",
            fontName=FONT_BOLD,
            fontSize=12.5,
            leading=16,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            fontName=FONT,
            fontSize=9.5,
            leading=14.2,
            textColor=INK,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small",
            fontName=FONT,
            fontSize=7.6,
            leading=10.5,
            textColor=MUTED,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            fontName=FONT,
            fontSize=9.2,
            leading=13.5,
            textColor=INK,
            leftIndent=12,
            firstLineIndent=-7,
            bulletIndent=0,
            spaceAfter=3,
        ),
        "callout": ParagraphStyle(
            "Callout",
            fontName=FONT_BOLD,
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#075985"),
            alignment=TA_CENTER,
        ),
        "table": ParagraphStyle(
            "Table",
            fontName=FONT,
            fontSize=7.6,
            leading=10,
            textColor=INK,
        ),
        "table_head": ParagraphStyle(
            "TableHead",
            fontName=FONT_BOLD,
            fontSize=7.7,
            leading=10,
            textColor=WHITE,
            alignment=TA_CENTER,
        ),
    }


def bullet(text: str, styles) -> Paragraph:
    return Paragraph(f"<bullet>&bull;</bullet>{text}", styles["bullet"])


def section_kicker(text: str, styles) -> Table:
    return Table(
        [[Paragraph(text.upper(), ParagraphStyle("k", parent=styles["small"], fontName=FONT_BOLD, textColor=BLUE))]],
        colWidths=[45 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BFDBFE")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        ),
        hAlign="LEFT",
    )


def capability_cards(styles):
    items = [
        ("01", "Grounded answers", "Uses retrieved guideline and research context instead of free-form generation."),
        ("02", "Traceable evidence", "Returns evidence snippets, sources, metadata, and a retrieval-derived confidence score."),
        ("03", "Managed knowledge", "Supports PDF upload, deletion, source status, and explicit collection rebuilds."),
        ("04", "Safety boundary", "Screens prompt injection and personalized or overconfident medical advice at the API edge."),
    ]
    cells = []
    for number, title, body in items:
        cells.append(
            [
                para(f"<font color='#2563EB'><b>{number}</b></font><br/><b>{title}</b><br/><font color='#627D98'>{body}</font>", styles["table"])
            ]
        )
    table = Table([[cells[0][0], cells[1][0]], [cells[2][0], cells[3][0]]], colWidths=[84 * mm, 84 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return table


def header_footer(canvas, doc):
    canvas.saveState()
    page = canvas.getPageNumber()
    if page > 1:
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, A4[1] - 17 * mm, A4[0] - doc.rightMargin, A4[1] - 17 * mm)
        canvas.setFont(FONT_BOLD, 7.3)
        canvas.setFillColor(NAVY)
        canvas.drawString(doc.leftMargin, A4[1] - 13 * mm, "MedRAG  |  Project Report")
        canvas.setFont(FONT, 7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(A4[0] - doc.rightMargin, A4[1] - 13 * mm, "Clinical guideline Q&A")
    canvas.setStrokeColor(LINE)
    canvas.line(doc.leftMargin, 14 * mm, A4[0] - doc.rightMargin, 14 * mm)
    canvas.setFont(FONT, 6.8)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 9 * mm, "Educational decision support only - not a substitute for professional medical judgment")
    canvas.drawRightString(A4[0] - doc.rightMargin, 9 * mm, f"{page:02d}")
    canvas.restoreState()


def build_report():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=23 * mm,
        bottomMargin=19 * mm,
        title="MedRAG Project Report",
        author="MedRAG Project Team",
        subject="Evidence-grounded clinical guideline question answering",
    )

    story = []
    story += [Spacer(1, 10 * mm), section_kicker("Project report", styles), Spacer(1, 8 * mm)]
    story += [para("MedRAG", styles["title"])]
    story += [para("Evidence-grounded clinical guideline question answering", styles["subtitle"])]

    hero = Table(
        [
            [
                para(
                    "<b>From scattered clinical evidence to a traceable answer.</b><br/>"
                    "MedRAG retrieves relevant passages from indexed guidelines and PubMed abstracts, then uses an LLM to generate a concise answer with evidence, sources, and confidence.",
                    styles["body"],
                )
            ]
        ],
        colWidths=[170 * mm],
    )
    hero.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#BFDBFE")),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story += [hero, Spacer(1, 10 * mm)]
    story += [para("Problem statement", styles["h1"])]
    story += [para("Clinical guidance is extensive, frequently updated, and distributed across long-form documents and research sources. Finding the most relevant passage and explaining it consistently is slow, while an unconstrained language model can produce answers without a reliable evidence trail.", styles["body"])]
    story += [para("Context", styles["h2"])]
    story += [para("MedRAG applies retrieval-augmented generation (RAG) to clinical guideline Q&A. A domain-agnostic core handles indexing, retrieval, generation, evaluation, and service orchestration. A MedRAG plugin supplies clinical ingestion rules, metadata, prompts, and safety policy.", styles["body"])]
    story += [para("Objectives", styles["h2"])]
    story += [
        bullet("Retrieve clinically relevant evidence from approved indexed sources.", styles),
        bullet("Generate readable answers that expose evidence and source provenance.", styles),
        bullet("Provide consistent access through CLI, FastAPI, and Streamlit interfaces.", styles),
        bullet("Reduce unsafe behavior with input and output guardrails and repeatable evaluations.", styles),
    ]
    story += [Spacer(1, 6 * mm), capability_cards(styles), PageBreak()]

    story += [section_kicker("Operating model", styles), Spacer(1, 5 * mm), para("How MedRAG works", styles["h1"])]
    intro = para("The system separates knowledge preparation from live question answering. Indexing is explicit and repeatable; query-time work stays focused on safety checks, retrieval, generation, and structured response delivery.", styles["body"])
    story += [intro, Spacer(1, 4 * mm)]
    workflow = [
        [para("Stage", styles["table_head"]), para("Conventional search", styles["table_head"]), para("MedRAG workflow", styles["table_head"]), para("System output", styles["table_head"])],
        [para("Source preparation", styles["table"]), para("Manually locate and scan documents", styles["table"]), para("Parse PDFs and fetch configured PubMed abstracts", styles["table"]), para("Normalized clinical documents", styles["table"])],
        [para("Knowledge organization", styles["table"]), para("Rely on filenames or ad hoc notes", styles["table"]), para("Chunk, enrich metadata, embed, and index in Qdrant", styles["table"]), para("Searchable evidence collection", styles["table"])],
        [para("Question answering", styles["table"]), para("Open documents and synthesize manually", styles["table"]), para("Retrieve top-k context and generate a grounded answer", styles["table"]), para("Answer, evidence, sources, confidence", styles["table"])],
        [para("Quality and safety", styles["table"]), para("Depends on individual review practice", styles["table"]), para("Run API guardrails and DeepEval quality metrics", styles["table"]), para("Blocked unsafe output or assessed response", styles["table"])],
    ]
    table = Table(workflow, colWidths=[30 * mm, 43 * mm, 56 * mm, 41 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE_BLUE]),
                ("GRID", (0, 0), (-1, -1), 0.5, WHITE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story += [table, Spacer(1, 7 * mm)]
    story += [para("Key inputs", styles["h2"])]
    story += [
        bullet("Clinical guideline PDFs placed in or uploaded to the MedRAG guideline source directory.", styles),
        bullet("Configured PubMed search queries and retrieval limits.", styles),
        bullet("Runtime credentials for OpenAI and LlamaParse; Groq is optional for guardrails.", styles),
        bullet("Index configuration: embedding model, chunk size, overlap, query mode, and top-k.", styles),
    ]
    story += [para("Structured output", styles["h2"])]
    output_data = [
        [para("Answer", styles["table_head"]), para("Evidence", styles["table_head"]), para("Sources", styles["table_head"]), para("Confidence", styles["table_head"])],
        [para("Guideline-level natural-language synthesis", styles["table"]), para("Retrieved supporting snippets", styles["table"]), para("Source file, title, organization, specialty, evidence type", styles["table"]), para("Retrieval-derived score when available", styles["table"])],
    ]
    out_table = Table(output_data, colWidths=[45 * mm, 42 * mm, 50 * mm, 33 * mm])
    out_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [out_table, Spacer(1, 7 * mm)]
    note = Table([[para("No time-saving benchmark is claimed here: the repository defines the automation path, but does not contain a controlled productivity study.", styles["callout"])]], colWidths=[170 * mm])
    note.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE_AMBER), ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#F59E0B")), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [note, PageBreak()]

    story += [section_kicker("System design", styles), Spacer(1, 5 * mm), para("Architecture", styles["h1"])]
    story += [para("One shared RAG service coordinates a plugin-based core. The MedRAG project definition selects its clinical configuration and ingestor; the three interfaces reuse the same retrieval and generation path.", styles["body"]), Spacer(1, 3 * mm)]
    story += [ArchitectureDiagram(170 * mm), Spacer(1, 7 * mm)]
    steps = [
        ("1. Collect and parse", "LlamaParse converts clinical guideline PDFs to structured text. The PubMed reader adds abstracts from configured searches. Optional bootstrap documents support demonstrations."),
        ("2. Enrich and index", "MedRAG labels each document with source organization, specialty, and evidence type. Sentence chunks are embedded locally with BAAI/bge-small-en-v1.5 and written to a named Qdrant collection."),
        ("3. Retrieve and generate", "A user question becomes a vector search. The selected evidence is inserted into the clinical system prompt, and OpenAI generates a concise educational response."),
        ("4. Validate and return", "At the API boundary, the answer is checked against the MedRAG safety policy. The API returns a typed response containing answer, evidence, source metadata, and confidence."),
    ]
    rows = []
    for title, body in steps:
        rows.append([para(f"<b>{title}</b>", styles["body"]), para(body, styles["body"])])
    steps_table = Table(rows, colWidths=[40 * mm, 130 * mm])
    steps_table.setStyle(TableStyle([("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, colors.HexColor("#F8FAFC")]), ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [steps_table, PageBreak()]

    story += [section_kicker("Implementation", styles), Spacer(1, 5 * mm), para("Core modules and responsibilities", styles["h1"])]
    modules = [
        [para("Layer", styles["table_head"]), para("Primary modules", styles["table_head"]), para("Responsibility", styles["table_head"])],
        [para("Interfaces", styles["table"]), para("src/cli.py<br/>src/api/main.py<br/>src/ui/app.py", styles["table"]), para("Developer commands, typed HTTP endpoints, and an interactive Streamlit client.", styles["table"])],
        [para("Service", styles["table"]), para("src/core/service.py", styles["table"]), para("Creates a project-specific service, builds or loads the index, and coordinates queries.", styles["table"])],
        [para("RAG core", styles["table"]), para("indexer.py<br/>retriever.py<br/>generator.py", styles["table"]), para("Chunks and embeds documents, retrieves evidence, builds prompts, and parses structured answers.", styles["table"])],
        [para("Project plugin", styles["table"]), para("projects/medrag/config.py<br/>projects/medrag/ingestor.py", styles["table"]), para("Defines clinical prompts, metadata, collection settings, safety policy, and source ingestion.", styles["table"])],
        [para("Operations", styles["table"]), para("source_manager.py<br/>evals.py<br/>docker-compose*.yml", styles["table"]), para("Manages source files, runs quality checks, and packages local or production services.", styles["table"])],
    ]
    mod_table = Table(modules, colWidths=[28 * mm, 58 * mm, 84 * mm], repeatRows=1)
    mod_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE_BLUE]), ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [mod_table, Spacer(1, 7 * mm)]
    story += [para("API surface", styles["h2"])]
    endpoints = [
        ("Knowledge", "GET /sources, POST /sources/upload, DELETE /sources/{filename}, POST /sources/reindex"),
        ("Question answering", "POST /query"),
        ("Safety diagnostics", "GET /guardrails/status, POST /guardrails/test-input, POST /guardrails/test-output"),
        ("Evaluation", "POST /evals/medrag/run, GET /evals/medrag/latest"),
        ("Operations", "GET /health"),
    ]
    ep_rows = [[para(f"<b>{name}</b>", styles["body"]), para(value, styles["body"])] for name, value in endpoints]
    ep_table = Table(ep_rows, colWidths=[42 * mm, 128 * mm])
    ep_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), PALE_MINT), ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [ep_table, Spacer(1, 7 * mm)]
    story += [para("Deployment topology", styles["h2"])]
    story += [para("Docker Compose runs Qdrant, a one-shot indexer, FastAPI, and Streamlit. The indexer waits for Qdrant and prepares the collection; the API starts after indexing; the UI calls only the API. Production assets add Nginx, EC2 bootstrap scripts, CloudFormation infrastructure, and GitHub Actions workflows.", styles["body"])]
    story += [PageBreak()]

    story += [section_kicker("Trust and quality", styles), Spacer(1, 5 * mm), para("Safety, evaluation, and operational controls", styles["h1"])]
    safety = [
        [para("Control", styles["table_head"]), para("Implemented behavior", styles["table_head"]), para("Important boundary", styles["table_head"])],
        [para("Input guardrail", styles["table"]), para("Groq-hosted Prompt Guard estimates whether a query is malicious or attempts prompt injection.", styles["table"]), para("Runs only on POST /query and dedicated guardrail tests; CLI and eval calls bypass it.", styles["table"])],
        [para("Output guardrail", styles["table"]), para("A project policy flags direct dosage instructions, personalized diagnosis or treatment, and overstated certainty.", styles["table"]), para("Policy classification is a safety layer, not clinical review or regulatory approval.", styles["table"])],
        [para("Failure behavior", styles["table"]), para("Missing key, timeout, network failure, or malformed model output is logged and allowed through.", styles["table"]), para("The current design fails open to preserve availability; production risk owners should explicitly accept or change this posture.", styles["table"])],
        [para("Evaluation", styles["table"]), para("DeepEval measures faithfulness, answer relevancy, and contextual relevancy against a golden dataset.", styles["table"]), para("Scores are model- and dataset-dependent; they do not establish patient outcome benefit.", styles["table"])],
    ]
    saf_table = Table(safety, colWidths=[30 * mm, 74 * mm, 66 * mm], repeatRows=1)
    saf_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE_AMBER]), ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [saf_table, Spacer(1, 7 * mm)]
    story += [para("Operational checklist", styles["h2"])]
    checks = [
        "Use only sources that the deployment is authorized to process and retain.",
        "Keep the source collection current, then rebuild the index after source changes.",
        "Protect API keys and never commit populated environment files.",
        "Review retrieved evidence and answers for clinical appropriateness before relying on them.",
        "Run automated tests and the golden-dataset evaluation after prompt, model, embedding, or retrieval changes.",
        "Monitor guardrail availability, response failures, latency, and source freshness in production.",
    ]
    story += [bullet(item, styles) for item in checks]
    risk = Table([[para("MedRAG should be positioned as an educational evidence assistant. It does not diagnose, prescribe, replace a clinician, or guarantee that indexed guidance is complete or current.", styles["callout"])]], colWidths=[170 * mm])
    risk.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE_AMBER), ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#F59E0B")), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story += [Spacer(1, 7 * mm), risk, PageBreak()]

    story += [section_kicker("Product experience", styles), Spacer(1, 5 * mm), para("Product walkthrough", styles["h1"])]
    story += [para("The Streamlit application is a thin HTTP client over the FastAPI service. It centralizes knowledge management, question answering, evaluation results, and guardrail diagnostics without embedding retrieval logic in the UI.", styles["body"]), Spacer(1, 3 * mm)]
    story += [ProductMockup(170 * mm), Spacer(1, 4 * mm)]
    story += [para("Typical user flow", styles["h2"])]
    flow = [
        [para("1", styles["table_head"]), para("Prepare", styles["table_head"]), para("Upload approved guideline PDFs and inspect PubMed ingestion settings.", styles["table"])],
        [para("2", styles["table_head"]), para("Index", styles["table_head"]), para("Rebuild the Qdrant collection so new or removed sources affect retrieval.", styles["table"])],
        [para("3", styles["table_head"]), para("Ask", styles["table_head"]), para("Submit a clinical guideline question through the UI or POST /query.", styles["table"])],
        [para("4", styles["table_head"]), para("Review", styles["table_head"]), para("Read the answer together with evidence snippets, sources, and confidence.", styles["table"])],
        [para("5", styles["table_head"]), para("Assess", styles["table_head"]), para("Run the evaluation suite and guardrail diagnostics after meaningful system changes.", styles["table"])],
    ]
    flow_table = Table(flow, colWidths=[12 * mm, 28 * mm, 130 * mm])
    flow_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (1, -1), BLUE), ("ROWBACKGROUNDS", (2, 0), (2, -1), [WHITE, PALE_BLUE]), ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [flow_table, Spacer(1, 4 * mm)]
    story += [para("Project status and next priorities", styles["h2"])]
    story += [
        bullet("Current scope: RAG core, MedRAG plugin, source management, typed API, Streamlit UI, evaluations, Docker/AWS deployment assets, and feature-branch I/O guardrails.", styles),
        bullet("Next: set product quality thresholds, expand the clinician-reviewed golden dataset, and choose a monitored production failure policy for guardrails.", styles),
        bullet("Before sensitive use: add authentication, authorization, audit logging, retention rules, and formal privacy, security, and clinical review.", styles),
    ]
    story += [Spacer(1, 3 * mm), para("Prepared from the MedRAG repository implementation and the supplied report's presentation pattern. Repository state reviewed 23 August 2026.", styles["small"])]

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    build_report()
