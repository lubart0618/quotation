from __future__ import annotations

import os
import re
from pathlib import Path
from io import BytesIO

from flask import Flask, make_response, redirect, render_template, request, send_file, url_for
from PIL import Image as PILImage, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from scheduler import Employee, Event, LeaveRecord, build_summary, schedule
from store import (
    DEFAULT_BRANDS,
    DEFAULT_GROUPS,
    DEFAULT_STORES,
    execute,
    init_db,
    query_all,
    seed_defaults,
)


BASE_DIR = Path(__file__).resolve().parent
WEEKDAY_OPTIONS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SLOT_OPTIONS = ["AM", "PM"]
LEAVE_SLOT_OPTIONS = ["AM", "PM", "FULL"]


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

CJK_FONT = "Huninn"
CJK_FONT_PATH = BASE_DIR / "assets" / "fonts" / "jf-openhuninn.ttf"
registerFont(TTFont(CJK_FONT, str(CJK_FONT_PATH)))


SITE_URL = "https://zhongli-seo.example.com"
SITE_NAME = "中壢在地 SEO 工作室"
SITE_PHONE = "03-425-9008"
SITE_ADDRESS = "桃園市中壢區中正路 168 號 8 樓"
QUOTE_LOGO_PATH = Path("/Users/bart/Desktop/Mac/05_素材庫/巴哥 來了LOGO.png")
QUOTE_PROVIDER = {
    "company_name": "政大企業有限公司",
    "company_id": "69679201",
    "address": "桃園市中壢區福州路131號",
    "phone": "03-437-8585",
    "account_name": "政大企業有限公司",
    "bank_name": "中國信託銀行",
    "bank_code": "822",
    "account_number": "495540630985",
    "branch_name": "中原分行",
}


def bootstrap() -> None:
    init_db()
    seed_defaults()


def to_csv(values: list[str]) -> str:
    return ",".join(value for value in values if value)


def fetch_employees() -> list[dict]:
    return query_all(
        """
        SELECT
            id,
            name,
            groups_text,
            available_days,
            available_slots,
            weekly_max_shifts,
            priority,
            notes
        FROM employees
        ORDER BY name COLLATE NOCASE
        """
    )


def fetch_leaves() -> list[dict]:
    return query_all(
        """
        SELECT
            leaves.id,
            leaves.date,
            leaves.slot,
            leaves.reason,
            employees.name AS employee_name
        FROM leaves
        JOIN employees ON employees.id = leaves.employee_id
        ORDER BY leaves.date, leaves.slot, employees.name
        """
    )


def fetch_events() -> list[dict]:
    return query_all(
        """
        SELECT
            id,
            date,
            slot,
            store,
            brand,
            category,
            required_staff,
            preferred_group,
            notes
        FROM events
        ORDER BY date, slot, store, brand
        """
    )


def build_scheduler_inputs() -> tuple[dict[str, Employee], list[LeaveRecord], list[Event]]:
    employees = {}
    for row in fetch_employees():
        employee_id = f"E{row['id']:03d}"
        employees[employee_id] = Employee(
            employee_id=employee_id,
            name=row["name"],
            groups={part.strip().lower() for part in row["groups_text"].split(",") if part.strip()},
            available_days={part.strip() for part in row["available_days"].split(",") if part.strip()},
            available_slots={part.strip().upper() for part in row["available_slots"].split(",") if part.strip()},
            weekly_max_shifts=row["weekly_max_shifts"],
            priority=row["priority"],
            notes=row["notes"],
        )

    name_to_code = {row["name"]: f"E{row['id']:03d}" for row in fetch_employees()}
    leaves = []
    for row in fetch_leaves():
        employee_code = name_to_code.get(row["employee_name"])
        if employee_code:
            leaves.append(
                LeaveRecord(
                    employee_id=employee_code,
                    date=row["date"],
                    slot=row["slot"],
                    reason=row["reason"],
                )
            )

    events = []
    for row in fetch_events():
        events.append(
            Event(
                event_id=f"EV{row['id']:03d}",
                date=row["date"],
                slot=row["slot"],
                store=row["store"],
                brand=row["brand"],
                category=row["category"].lower(),
                required_staff=row["required_staff"],
                preferred_group=(row["preferred_group"] or row["category"]).lower(),
                notes=row["notes"],
            )
        )

    return employees, leaves, events


def dashboard_context(message: str | None = None, active_tab: str = "employees") -> dict:
    employees = fetch_employees()
    leaves = fetch_leaves()
    events = fetch_events()
    return {
        "message": message,
        "active_tab": active_tab,
        "employees": employees,
        "leaves": leaves,
        "events": events,
        "group_options": DEFAULT_GROUPS,
        "store_options": DEFAULT_STORES,
        "brand_options": DEFAULT_BRANDS,
        "weekday_options": WEEKDAY_OPTIONS,
        "slot_options": SLOT_OPTIONS,
        "leave_slot_options": LEAVE_SLOT_OPTIONS,
        "stats": {
            "employees": len(employees),
            "events": len(events),
            "leaves": len(leaves),
        },
    }


def seo_context() -> dict:
    site_url = os.environ.get("SITE_URL", "").rstrip("/") or request.url_root.rstrip("/")
    faq_items = [
        {
            "question": "中壢在地 SEO 和一般 SEO 公司有什麼差別？",
            "answer": "在地 SEO 會把商圈、行政區、通勤動線、Google 商家檔案與區域型關鍵字一起規劃，更適合中壢實體店面、診所、室內設計、法律與教育品牌。",
        },
        {
            "question": "多久會看到中壢 SEO 成效？",
            "answer": "通常 6 到 12 週可以看見關鍵字與自然流量開始成長，但實際速度會受網站基礎、競爭度與內容量影響。",
        },
        {
            "question": "你們會幫忙 Google 商家優化嗎？",
            "answer": "會，我們會同步處理 Google 商家檔案、評論策略、NAP 一致性與在地頁面內容，讓地圖與自然搜尋一起成長。",
        },
        {
            "question": "如果我主要客戶在中壢、內壢、青埔，也適合做這種網站嗎？",
            "answer": "適合，我們可以依照服務區域建立對應頁面與內容主題，把中壢、內壢、青埔等區域需求分開布局。",
        },
    ]
    local_business_schema = {
        "@context": "https://schema.org",
        "@type": "ProfessionalService",
        "name": SITE_NAME,
        "image": f"{site_url}/static/og-zhongli-seo.jpg",
        "url": site_url,
        "telephone": SITE_PHONE,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": SITE_ADDRESS,
            "addressLocality": "中壢區",
            "addressRegion": "桃園市",
            "addressCountry": "TW",
        },
        "areaServed": ["中壢區", "內壢", "青埔", "平鎮區", "楊梅區"],
        "priceRange": "$$",
        "description": "專做中壢在地商家 SEO、Google 商家優化、內容佈局與轉換頁設計。",
    }
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item["answer"],
                },
            }
            for item in faq_items
        ],
    }
    return {
        "site_name": SITE_NAME,
        "site_url": site_url,
        "site_phone": SITE_PHONE,
        "site_address": SITE_ADDRESS,
        "meta_title": "中壢 SEO 公司推薦｜中壢在地經營、Google 商家優化、網站自然排名",
        "meta_description": "提供中壢在地 SEO、Google 商家優化、內容規劃與轉換頁設計，幫助中壢店家在「中壢推薦」「中壢附近」「桃園中壢」相關搜尋中穩定曝光。",
        "hero_tags": ["中壢 SEO", "Google 商家優化", "在地關鍵字佈局", "桃園網站排名"],
        "service_cards": [
            {
                "eyebrow": "Local SEO",
                "title": "中壢商圈關鍵字布局",
                "body": "從中壢火車站、SOGO、內壢、青埔到工業區周邊，我們會依實際商圈意圖規劃頁面與內容。",
            },
            {
                "eyebrow": "Google Business Profile",
                "title": "地圖與商家檔案同步優化",
                "body": "把 Google 商家、評論策略、問答與網站內容串起來，提升地圖能見度與來電率。",
            },
            {
                "eyebrow": "Content Strategy",
                "title": "在地內容與常見問題頁",
                "body": "建立能吃到長尾搜尋的 FAQ、案例頁與服務頁，讓網站不只漂亮，也能持續累積排名。",
            },
        ],
        "process_steps": [
            "盤點目前網站、Google 商家與競品在中壢的能見度。",
            "定義核心關鍵字、服務區域頁與轉換頁架構。",
            "優化頁面標題、內容、內鏈、速度與結構化資料。",
            "每月追蹤排名、流量、詢問量與可再擴張的在地主題。",
        ],
        "proof_points": [
            {"label": "在地頁面架構", "value": "12+"},
            {"label": "可佈局長尾主題", "value": "40+"},
            {"label": "Google 商家優化項目", "value": "18"},
            {"label": "每月追蹤指標", "value": "6"},
        ],
        "districts": ["中壢市區", "內壢", "青埔", "平鎮", "楊梅", "A19 周邊"],
        "faq_items": faq_items,
        "local_business_schema": local_business_schema,
        "faq_schema": faq_schema,
    }


def money(value: int | float, html: bool = False) -> str:
    formatted = f"{value:,.0f}"
    if html:
        return f"NT$ {space_numeric_token(formatted, html=True)}"
    return f"NT$ {formatted}"


def space_digits_in_text(text: str, html: bool = False) -> str:
    if not html:
        return text
    return re.sub(
        r"\d[\d,.-]*",
        lambda match: space_numeric_token(match.group(0), html=True),
        text,
    )


def space_numeric_token(text: str, html: bool = False) -> str:
    spacer = "&thinsp;" if html else " "
    chars: list[str] = []
    for index, char in enumerate(text):
        chars.append(char)
        if index == len(text) - 1:
            continue
        next_char = text[index + 1]
        if char.isdigit() and next_char.isdigit():
            chars.append(spacer)
    return "".join(chars)


def build_round_logo_bytes(size: int = 720) -> bytes | None:
    if not QUOTE_LOGO_PATH.exists():
        return None

    with PILImage.open(QUOTE_LOGO_PATH).convert("RGBA") as image:
        square = ImageOps.fit(image, (size, size), method=PILImage.Resampling.LANCZOS)
        mask = PILImage.new("L", (size, size), 0)
        mask_draw = PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
        mask_canvas = PILImage.new("L", (size, size), 0)
        draw_image = PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
        # Pillow ellipse drawing is only needed once; use paste with a circular mask.
        from PIL import ImageDraw

        draw = ImageDraw.Draw(mask_canvas)
        draw.ellipse((0, 0, size - 1, size - 1), fill=255)
        output = PILImage.new("RGBA", (size, size), (255, 255, 255, 0))
        output.paste(square, (0, 0), mask_canvas)
        buffer = BytesIO()
        output.save(buffer, format="PNG")
        return buffer.getvalue()


def build_quote_pdf(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "QuoteTitle",
        parent=styles["Title"],
        fontName=CJK_FONT,
        fontSize=18,
        textColor=colors.HexColor("#7a3614"),
        leading=22,
        alignment=1,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "QuoteBody",
        parent=styles["BodyText"],
        fontName=CJK_FONT,
        fontSize=10.5,
        leading=16,
        textColor=colors.HexColor("#1f1b16"),
    )
    small_style = ParagraphStyle(
        "QuoteSmall",
        parent=body_style,
        fontSize=9.5,
        textColor=colors.HexColor("#64584d"),
        leading=14,
    )
    label_style = ParagraphStyle(
        "QuoteLabel",
        parent=body_style,
        fontSize=9.5,
        textColor=colors.HexColor("#7a3614"),
        leading=14,
    )
    meta_style = ParagraphStyle(
        "QuoteMeta",
        parent=body_style,
        fontSize=10.5,
        leading=18,
        textColor=colors.HexColor("#1f1b16"),
    )
    qty_style = ParagraphStyle(
        "QuoteQty",
        parent=small_style,
        fontName=CJK_FONT,
        fontSize=10.5,
        alignment=1,
        leading=14,
        textColor=colors.HexColor("#4a4038"),
    )
    amount_style = ParagraphStyle(
        "QuoteAmount",
        parent=small_style,
        fontName=CJK_FONT,
        fontSize=11.5,
        alignment=2,
        leading=14,
        textColor=colors.HexColor("#4a4038"),
    )
    summary_label_style = ParagraphStyle(
        "QuoteSummaryLabel",
        parent=body_style,
        fontName=CJK_FONT,
        fontSize=10.5,
        alignment=0,
        leading=14,
        textColor=colors.HexColor("#1f1b16"),
    )
    summary_amount_style = ParagraphStyle(
        "QuoteSummaryAmount",
        parent=body_style,
        fontName=CJK_FONT,
        fontSize=12,
        alignment=2,
        leading=14,
        textColor=colors.HexColor("#1f1b16"),
    )
    summary_total_style = ParagraphStyle(
        "QuoteSummaryTotal",
        parent=summary_amount_style,
        textColor=colors.HexColor("#7a3614"),
    )

    items = data.get("items", [])
    subtotal = sum((item.get("qty", 0) or 0) * (item.get("price", 0) or 0) for item in items)
    tax_rate = max(float(data.get("taxRate", 0) or 0), 0)
    tax = round(subtotal * (tax_rate / 100))
    total = subtotal + tax
    executor = str(data.get("executor", "") or "")
    payment_method = space_digits_in_text(str(data.get("paymentTerms", "") or "-"), html=True)
    payment_method = payment_method.replace("：", "： ").replace(":", ": ").replace("\n", "<br/>")

    story = []
    logo_bytes = build_round_logo_bytes()
    if logo_bytes:
        logo = RLImage(BytesIO(logo_bytes), width=22 * mm, height=22 * mm)
        logo.hAlign = "CENTER"
        story.extend([logo, Spacer(1, 4)])
    story.extend([Paragraph("專案報價單", title_style), Spacer(1, 8)])

    header_table = Table(
        [
            [
                Paragraph(
                    f"客戶： {data.get('companyName', '')}<br/>"
                    f"聯絡人： {data.get('contactName', '')}<br/>"
                    f"電話： {space_digits_in_text(data.get('contactPhone', ''), html=True)}<br/>"
                    f"地址： {data.get('companyAddress', '')}",
                    body_style,
                ),
                Paragraph(
                    f"報價單號： {space_digits_in_text(data.get('quoteNumber', ''), html=True)}<br/>"
                    f"日期： {space_digits_in_text(data.get('quoteDate', ''), html=True)}<br/>"
                    f"報價有效期： {space_digits_in_text(data.get('validUntil', ''), html=True)}<br/>"
                    f"稅率： {space_digits_in_text(f'{tax_rate:.0f}%', html=True)}",
                    meta_style,
                ),
            ]
        ],
        colWidths=[98 * mm, 77 * mm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d9c5b4")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e7d9cc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend([header_table, Spacer(1, 10)])

    table_rows = [[Paragraph("項目", body_style), Paragraph("數量", body_style), Paragraph("單價", body_style), Paragraph("小計", body_style)]]
    for item in items:
        qty = item.get("qty", 0) or 0
        price = item.get("price", 0) or 0
        amount = qty * price
        table_rows.append(
            [
                Paragraph(str(item.get("name", "")), small_style),
                Paragraph(str(qty), qty_style),
                Paragraph(money(price, html=True), amount_style),
                Paragraph(money(amount, html=True), amount_style),
            ]
        )

    items_table = Table(table_rows, colWidths=[95 * mm, 20 * mm, 30 * mm, 30 * mm])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4e6da")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#7a3614")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9c5b4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend([items_table, Spacer(1, 12)])

    summary_table = Table(
        [
            [Paragraph("小計", summary_label_style), Paragraph(money(subtotal, html=True), summary_amount_style)],
            [Paragraph("稅額", summary_label_style), Paragraph(money(tax, html=True), summary_amount_style)],
            [Paragraph("總金額", summary_label_style), Paragraph(money(total, html=True), summary_total_style)],
        ],
        colWidths=[46 * mm, 46 * mm],
        hAlign="RIGHT",
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#f4e6da")),
                ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#7a3614")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d9c5b4")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e7d9cc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    footer_table = Table(
        [
            [
                Paragraph(
                    f"<font color='#7a3614'>報價提供者</font><br/>"
                    f"公司名稱： {QUOTE_PROVIDER['company_name']}<br/>"
                    f"統編： {space_digits_in_text(QUOTE_PROVIDER['company_id'], html=True)}<br/>"
                    f"地址： {QUOTE_PROVIDER['address']}<br/>"
                    f"電話： {space_digits_in_text(QUOTE_PROVIDER['phone'], html=True)}<br/>"
                    f"專案執行人： {space_digits_in_text(executor, html=True) if executor else '________________'}",
                    small_style,
                ),
                Paragraph(f"<font color='#7a3614'>付款方式</font><br/>{payment_method}", small_style),
                Paragraph("客戶用印處", label_style),
            ]
        ],
        colWidths=[65 * mm, 70 * mm, 40 * mm],
    )
    footer_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d9c5b4")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e7d9cc")),
                ("FONTNAME", (0, 0), (-1, -1), CJK_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 24),
                ("MINROWHEIGHT", (2, 0), (2, 0), 45 * mm),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 12), footer_table])

    doc.build(story)
    return buffer.getvalue()


@app.get("/")
def index():
    bootstrap()
    return render_template("landing.html", **seo_context())


@app.get("/quote")
def quote_builder():
    bootstrap()
    return render_template("quote_builder.html", logo_exists=QUOTE_LOGO_PATH.exists(), provider=QUOTE_PROVIDER)


@app.get("/quote/logo")
def quote_logo():
    logo_bytes = build_round_logo_bytes()
    if not logo_bytes:
        return "", 404
    return send_file(BytesIO(logo_bytes), mimetype="image/png")


@app.post("/quote/export-pdf")
def export_quote_pdf():
    bootstrap()
    data = request.get_json(silent=True) or {}
    pdf = build_quote_pdf(data)
    filename = f"{data.get('quoteNumber', 'quote')}.pdf"
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@app.post("/employees")
def add_employee():
    groups = request.form.getlist("groups")
    days = request.form.getlist("available_days")
    slots = request.form.getlist("available_slots")
    execute(
        """
        INSERT INTO employees
        (name, groups_text, available_days, available_slots, weekly_max_shifts, priority, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.form.get("name", "").strip(),
            to_csv(groups),
            to_csv(days),
            to_csv(slots),
            int(request.form.get("weekly_max_shifts", "5")),
            int(request.form.get("priority", "1")),
            request.form.get("notes", "").strip(),
        ),
    )
    return render_template("dashboard.html", **dashboard_context("已新增人員。", "employees"))


@app.post("/events")
def add_event():
    execute(
        """
        INSERT INTO events
        (date, slot, store, brand, category, required_staff, preferred_group, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.form.get("date", "").strip(),
            request.form.get("slot", "AM").strip(),
            request.form.get("store", "").strip(),
            request.form.get("brand", "").strip(),
            request.form.get("category", "").strip().lower(),
            int(request.form.get("required_staff", "1")),
            request.form.get("preferred_group", "").strip().lower() or request.form.get("category", "").strip().lower(),
            request.form.get("notes", "").strip(),
        ),
    )
    return render_template("dashboard.html", **dashboard_context("已新增場次。", "events"))


@app.post("/leaves")
def add_leave():
    employee_id = int(request.form.get("employee_id", "0"))
    execute(
        """
        INSERT INTO leaves (employee_id, date, slot, reason)
        VALUES (?, ?, ?, ?)
        """,
        (
            employee_id,
            request.form.get("date", "").strip(),
            request.form.get("slot", "FULL").strip(),
            request.form.get("reason", "").strip(),
        ),
    )
    return render_template("dashboard.html", **dashboard_context("已新增請假設定。", "leaves"))


@app.post("/seed/reset")
def reset_seed():
    seed_defaults(force=True)
    return render_template("dashboard.html", **dashboard_context("已重設成預設示範資料。", "employees"))


@app.post("/schedule/run")
def run_schedule():
    employees, leaves, events = build_scheduler_inputs()
    assignments, unfilled = schedule(employees, leaves, events)
    summary = build_summary(employees)
    return render_template(
        "planner.html",
        assignments=assignments,
        unfilled=unfilled,
        summary=summary,
        stats={
            "assignments": len(assignments),
            "unfilled": len(unfilled),
            "employees": len(summary),
            "events": len(events),
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/reload")
def reload_home():
    return redirect(url_for("index"))


if __name__ == "__main__":
    bootstrap()
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=False, host="0.0.0.0", port=port)
