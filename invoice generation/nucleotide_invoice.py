"""
Nucleotide Healthcare - Invoice / Bill of Supply PDF Generator
==============================================================
Generates professional invoices styled after the Healthians format,
branded with Nucleotide's logo, colors, and company details.

Usage:
    from nucleotide_invoice import generate_invoice
    generate_invoice(invoice_data, output_path="invoice.pdf")

See `SAMPLE_INVOICE` at the bottom for a complete parameter reference.
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, Color, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
    HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from num2words import num2words
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ──────────────────────────────────────────────────────────────
# FONT REGISTRATION (DejaVu Sans supports ₹ symbol)
# ──────────────────────────────────────────────────────────────
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts") + os.sep
pdfmetrics.registerFont(TTFont('DVSans',       _FONT_DIR + 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVSans-Bold',  _FONT_DIR + 'DejaVuSans-Bold.ttf'))
pdfmetrics.registerFont(TTFont('DVSans-Oblique', _FONT_DIR + 'DejaVuSans-Oblique.ttf'))
pdfmetrics.registerFont(TTFont('DVSans-BoldOblique', _FONT_DIR + 'DejaVuSans-BoldOblique.ttf'))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily(
    'DVSans',
    normal='DVSans', bold='DVSans-Bold',
    italic='DVSans-Oblique', boldItalic='DVSans-BoldOblique',
)

FONT       = 'DVSans'
FONT_BOLD  = 'DVSans-Bold'
FONT_ITAL  = 'DVSans-Oblique'

# ──────────────────────────────────────────────────────────────
# BRAND CONSTANTS (derived from Nucleotide logo / website)
# ──────────────────────────────────────────────────────────────
TEAL_PRIMARY   = HexColor("#1A9E8F")   # Primary teal from logo
TEAL_LIGHT     = HexColor("#2EC4B6")   # Lighter teal accent
PURPLE_PRIMARY = HexColor("#9B7BF7")   # Purple from logo helix
DARK_TEXT       = HexColor("#2D3748")   # Dark charcoal for body text
LIGHT_GRAY     = HexColor("#F7F8FA")   # Table row alternate
MID_GRAY       = HexColor("#E2E8F0")   # Table borders
HEADER_BG      = HexColor("#1A9E8F")   # Header bar background
SUBTLE_TEXT     = HexColor("#A0AEC0")   # For subtle info like PAN
RED_DISCOUNT    = HexColor("#E53E3E")   # Discount highlight

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────
def amount_in_words(amount: float) -> str:
    """Convert a numeric amount to Indian-English words for invoices."""
    rupees = int(amount)
    paise = round((amount - rupees) * 100)
    words = num2words(rupees, lang='en_IN').replace(',', '')
    words = words.title()
    result = f"Rupees {words}"
    if paise > 0:
        paise_words = num2words(paise, lang='en_IN').title()
        result += f" and {paise_words} Paise"
    result += " Only"
    return result


def fmt_currency(value, symbol="₹") -> str:
    """Format an amount with Indian comma grouping."""
    if value is None:
        return ""
    val = float(value)
    is_negative = val < 0
    val = abs(val)
    integer_part = int(val)
    decimal_part = round((val - integer_part) * 100)

    s = str(integer_part)
    if len(s) > 3:
        last3 = s[-3:]
        remaining = s[:-3]
        # Indian grouping: pairs from right after first 3
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        s = ",".join(groups) + "," + last3
    
    result = f"{symbol}{s}"
    if decimal_part > 0:
        result += f".{decimal_part:02d}"
    else:
        result += ".00"
    if is_negative:
        result = f"-{result}"
    return result


def _get_styles():
    """Build paragraph styles for the invoice."""
    base = getSampleStyleSheet()
    styles = {}
    
    styles['title'] = ParagraphStyle(
        'InvoiceTitle', parent=base['Normal'],
        fontName=FONT_BOLD, fontSize=18,
        textColor=DARK_TEXT, spaceAfter=2 * mm,
    )
    styles['subtitle'] = ParagraphStyle(
        'InvoiceSubtitle', parent=base['Normal'],
        fontName=FONT, fontSize=9,
        textColor=DARK_TEXT, leading=13,
    )
    styles['heading'] = ParagraphStyle(
        'SectionHeading', parent=base['Normal'],
        fontName=FONT_BOLD, fontSize=10,
        textColor=TEAL_PRIMARY, spaceBefore=3 * mm, spaceAfter=2 * mm,
    )
    styles['label'] = ParagraphStyle(
        'FieldLabel', parent=base['Normal'],
        fontName=FONT_BOLD, fontSize=8.5,
        textColor=DARK_TEXT,
    )
    styles['value'] = ParagraphStyle(
        'FieldValue', parent=base['Normal'],
        fontName=FONT, fontSize=8.5,
        textColor=DARK_TEXT, leading=12,
    )
    styles['value_right'] = ParagraphStyle(
        'FieldValueRight', parent=base['Normal'],
        fontName=FONT, fontSize=8.5,
        textColor=DARK_TEXT, alignment=TA_RIGHT,
    )
    styles['table_header'] = ParagraphStyle(
        'TableHeader', parent=base['Normal'],
        fontName=FONT_BOLD, fontSize=8,
        textColor=white, leading=11,
    )
    styles['table_cell'] = ParagraphStyle(
        'TableCell', parent=base['Normal'],
        fontName=FONT, fontSize=8,
        textColor=DARK_TEXT, leading=11,
    )
    styles['table_cell_right'] = ParagraphStyle(
        'TableCellRight', parent=base['Normal'],
        fontName=FONT, fontSize=8,
        textColor=DARK_TEXT, alignment=TA_RIGHT, leading=11,
    )
    styles['total_label'] = ParagraphStyle(
        'TotalLabel', parent=base['Normal'],
        fontName=FONT_BOLD, fontSize=9.5,
        textColor=DARK_TEXT,
    )
    styles['total_value'] = ParagraphStyle(
        'TotalValue', parent=base['Normal'],
        fontName=FONT_BOLD, fontSize=9.5,
        textColor=DARK_TEXT, alignment=TA_RIGHT,
    )
    styles['grand_total_value'] = ParagraphStyle(
        'GrandTotalValue', parent=base['Normal'],
        fontName=FONT_BOLD, fontSize=12,
        textColor=TEAL_PRIMARY, alignment=TA_RIGHT,
    )
    styles['discount_value'] = ParagraphStyle(
        'DiscountValue', parent=base['Normal'],
        fontName=FONT_BOLD, fontSize=9.5,
        textColor=RED_DISCOUNT, alignment=TA_RIGHT,
    )
    styles['subtle'] = ParagraphStyle(
        'SubtleText', parent=base['Normal'],
        fontName=FONT, fontSize=7,
        textColor=SUBTLE_TEXT, leading=9,
    )
    styles['footer'] = ParagraphStyle(
        'FooterText', parent=base['Normal'],
        fontName=FONT, fontSize=7.5,
        textColor=DARK_TEXT, alignment=TA_CENTER, leading=10,
    )
    styles['words'] = ParagraphStyle(
        'AmountWords', parent=base['Normal'],
        fontName=FONT_ITAL, fontSize=8,
        textColor=DARK_TEXT, leading=11,
    )
    return styles


# ──────────────────────────────────────────────────────────────
# CUSTOM PAGE TEMPLATE (header/footer on every page)
# ──────────────────────────────────────────────────────────────
class InvoiceTemplate:
    """Draws repeating page elements — top accent bar and page footer."""

    def __init__(self, invoice_data, logo_path):
        self.data = invoice_data
        self.logo_path = logo_path

    def on_page(self, c: canvas.Canvas, doc):
        c.saveState()
        # Top accent bar
        c.setFillColor(TEAL_PRIMARY)
        c.rect(0, PAGE_H - 4 * mm, PAGE_W, 4 * mm, fill=True, stroke=False)
        # Thin purple sub-line
        c.setFillColor(PURPLE_PRIMARY)
        c.rect(0, PAGE_H - 5.2 * mm, PAGE_W, 1.2 * mm, fill=True, stroke=False)
        
        # Footer line
        c.setStrokeColor(MID_GRAY)
        c.setLineWidth(0.5)
        c.line(MARGIN, 18 * mm, PAGE_W - MARGIN, 18 * mm)
        
        # Footer text with clickable email and website links
        SEP = "  |  "
        parts = []
        customer_care = self.data.get("customer_care_phone")
        email = self.data.get("customer_care_email", "info@nucleotide.life")
        website = self.data.get("website", "www.nucleotide.life")
        if customer_care:
            parts.append(("text", f"Customer care: {customer_care}"))
        if email:
            parts.append(("email", email))
        if website:
            parts.append(("url", website))

        c.setFont(FONT, 7)
        c.setFillColor(DARK_TEXT)

        full_text = SEP.join(p[1] for p in parts)
        x = PAGE_W / 2 - c.stringWidth(full_text, FONT, 7) / 2
        y = 12 * mm

        LINK_COLOR = HexColor("#1A73E8")
        for i, (kind, text) in enumerate(parts):
            if i > 0:
                c.setFillColor(DARK_TEXT)
                c.drawString(x, y, SEP)
                x += c.stringWidth(SEP, FONT, 7)
            w = c.stringWidth(text, FONT, 7)
            if kind in ("email", "url"):
                c.setFillColor(LINK_COLOR)
                c.drawString(x, y, text)
                # Underline
                c.setStrokeColor(LINK_COLOR)
                c.setLineWidth(0.4)
                c.line(x, y - 0.5 * mm, x + w, y - 0.5 * mm)
                if kind == "email":
                    c.linkURL(f"mailto:{text}", (x, y - 1 * mm, x + w, y + 3 * mm))
                else:
                    url = text if text.startswith("http") else f"https://{text}"
                    c.linkURL(url, (x, y - 1 * mm, x + w, y + 3 * mm))
            else:
                c.setFillColor(DARK_TEXT)
                c.drawString(x, y, text)
            x += w
        
        # Page number
        c.setFont(FONT, 6.5)
        c.setFillColor(SUBTLE_TEXT)
        c.drawRightString(PAGE_W - MARGIN, 8 * mm, f"Page {c.getPageNumber()}")
        
        c.restoreState()


# ──────────────────────────────────────────────────────────────
# MAIN GENERATOR
# ──────────────────────────────────────────────────────────────
def generate_invoice(data: dict, output_path: str = "invoice.pdf", logo_path: str = None):
    """
    Generate a Nucleotide Healthcare invoice PDF.

    Parameters
    ----------
    data : dict
        Invoice data. See SAMPLE_INVOICE at the bottom for full schema.
    output_path : str
        Path for the output PDF file.
    logo_path : str or None
        Path to the Nucleotide logo image. If None, text fallback is used.

    Returns
    -------
    str : The output file path.
    """
    styles = _get_styles()
    template = InvoiceTemplate(data, logo_path)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=10 * mm,
        bottomMargin=22 * mm,
    )

    story = []

    # ── LOGO + TITLE ROW ──────────────────────────────────
    logo_cell = ""
    if logo_path and os.path.exists(logo_path):
        try:
            logo_cell = Image(logo_path, width=52 * mm, height=16 * mm, kind='proportional')
        except Exception:
            logo_cell = Paragraph(
                '<font color="#1A9E8F"><b>Nucleotide</b></font>',
                styles['title']
            )
    else:
        logo_cell = Paragraph(
            '<font color="#1A9E8F"><b>Nucleotide</b></font>',
            styles['title']
        )

    title_text = Paragraph("Bill of Supply", styles['title'])

    header_table = Table(
        [[logo_cell, title_text]],
        colWidths=[(PAGE_W - 2 * MARGIN) * 0.55, (PAGE_W - 2 * MARGIN) * 0.45],
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 3 * mm))

    # ── META INFO BAR (Invoice#, Date, Order#, SAC) ───────
    meta_fields = []
    meta_values = []

    if data.get("invoice_number"):
        meta_fields.append(Paragraph("INVOICE NO.", styles['label']))
        meta_values.append(Paragraph(str(data["invoice_number"]), styles['value']))
    if data.get("invoice_date"):
        meta_fields.append(Paragraph("INVOICE DATE", styles['label']))
        meta_values.append(Paragraph(str(data["invoice_date"]), styles['value']))
    if data.get("order_number"):
        meta_fields.append(Paragraph("ORDER NO.", styles['label']))
        meta_values.append(Paragraph(str(data["order_number"]), styles['value']))
    if data.get("sac_code"):
        meta_fields.append(Paragraph("SAC CODE", styles['label']))
        meta_values.append(Paragraph(str(data["sac_code"]), styles['value']))

    if meta_fields:
        n = len(meta_fields)
        col_w = (PAGE_W - 2 * MARGIN) / n
        meta_table = Table(
            [meta_fields, meta_values],
            colWidths=[col_w] * n,
        )
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), LIGHT_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 3 * mm),
            ('BOX', (0, 0), (-1, -1), 0.5, MID_GRAY),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, MID_GRAY),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 4 * mm))

    # ── BILL FROM / CUSTOMER BILLING ──────────────────────
    company_name = data.get("company_name", "Nucleotide Healthcare Pvt Ltd")
    company_address = data.get("company_address", "")
    gst_no = data.get("gst_number")

    bill_from_lines = [f'<b>{company_name}</b>']
    if company_address:
        bill_from_lines.append(company_address)
    if gst_no:
        bill_from_lines.append(f'GST No.: {gst_no}')
    bill_from_text = "<br/>".join(bill_from_lines)

    customer_name = data.get("customer_name", "")
    customer_address = data.get("customer_address", "")
    billing_lines = []
    if customer_name:
        billing_lines.append(f'<b>{customer_name}</b>')
    if customer_address:
        billing_lines.append(customer_address)
    billing_text = "<br/>".join(billing_lines)

    bill_table_data = [
        [
            Paragraph('<font color="#1A9E8F"><b>BILL FROM</b></font>', styles['label']),
            Paragraph('<font color="#1A9E8F"><b>CUSTOMER BILLING DETAILS</b></font>', styles['label']),
        ],
        [
            Paragraph(bill_from_text, styles['value']),
            Paragraph(billing_text, styles['value']),
        ],
    ]
    half_w = (PAGE_W - 2 * MARGIN) / 2
    bill_table = Table(bill_table_data, colWidths=[half_w, half_w])
    bill_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
        ('LINEBELOW', (0, 0), (-1, 0), 0.75, TEAL_PRIMARY),
        ('BOX', (0, 0), (-1, -1), 0.3, MID_GRAY),
    ]))
    story.append(bill_table)
    story.append(Spacer(1, 4 * mm))

    # ── DESCRIPTION (if provided) ─────────────────────────
    description = data.get("description")
    if description:
        story.append(Paragraph(f"<b>Description:</b> {description}", styles['value']))
        story.append(Spacer(1, 3 * mm))

    # ── LINE ITEMS TABLE ──────────────────────────────────
    # Supports two modes:
    #   1) "items" — product-level entries (Genetic one - single, etc.)
    #   2) "detailed_items" — per-person test breakdowns (like Healthians)
    # Both can coexist if provided.

    items = data.get("items", [])
    detailed_items = data.get("detailed_items", [])
    usable_w = PAGE_W - 2 * MARGIN

    if detailed_items:
        # ── DETAILED MODE (per-person, like Healthians) ───
        story.append(Paragraph("Test Details", styles['heading']))

        for person_block in detailed_items:
            person_name = person_block.get("person_name", "")
            tests = person_block.get("tests", [])

            # Person name header
            story.append(Paragraph(
                f'<font color="#1A9E8F"><b>{person_name}</b></font>',
                styles['value']
            ))
            story.append(Spacer(1, 1.5 * mm))

            # Build test table
            header_row = [
                Paragraph("TEST DESCRIPTION", styles['table_header']),
                Paragraph("AMOUNT", styles['table_header']),
            ]
            t_rows = [header_row]
            for test in tests:
                t_rows.append([
                    Paragraph(test.get("name", ""), styles['table_cell']),
                    Paragraph(fmt_currency(test.get("amount", 0)), styles['table_cell_right']),
                ])

            detail_table = Table(t_rows, colWidths=[usable_w * 0.72, usable_w * 0.28])
            detail_style = [
                ('BACKGROUND', (0, 0), (-1, 0), TEAL_PRIMARY),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
                ('LEFTPADDING', (0, 0), (-1, -1), 2.5 * mm),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2.5 * mm),
                ('GRID', (0, 0), (-1, -1), 0.3, MID_GRAY),
            ]
            # Alternate row shading
            for i in range(1, len(t_rows)):
                if i % 2 == 0:
                    detail_style.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY))
            detail_table.setStyle(TableStyle(detail_style))
            story.append(detail_table)
            story.append(Spacer(1, 3 * mm))

    if items:
        # ── PRODUCT-LEVEL MODE ────────────────────────────
        story.append(Paragraph("Product Summary", styles['heading']))

        header_row = [
            Paragraph("PRODUCT", styles['table_header']),
            Paragraph("AMOUNT", styles['table_header']),
        ]
        p_rows = [header_row]
        for item in items:
            p_rows.append([
                Paragraph(item.get("name", ""), styles['table_cell']),
                Paragraph(fmt_currency(item.get("amount", 0)), styles['table_cell_right']),
            ])

        prod_table = Table(p_rows, colWidths=[usable_w * 0.72, usable_w * 0.28])
        prod_style = [
            ('BACKGROUND', (0, 0), (-1, 0), TEAL_PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5 * mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 2.5 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2.5 * mm),
            ('GRID', (0, 0), (-1, -1), 0.3, MID_GRAY),
        ]
        for i in range(1, len(p_rows)):
            if i % 2 == 0:
                prod_style.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY))
        prod_table.setStyle(TableStyle(prod_style))
        story.append(prod_table)
        story.append(Spacer(1, 4 * mm))

    # ── TOTALS SECTION ────────────────────────────────────
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=MID_GRAY,
        spaceBefore=2 * mm, spaceAfter=3 * mm,
    ))

    total_amount = data.get("total_amount", 0)
    discount_coupon = data.get("discount_coupon")  # e.g. {"code": "CC2500", "amount": 2500}
    grand_total = data.get("grand_total", total_amount)
    paid_amount = data.get("paid_amount", grand_total)

    totals_rows = []

    # Total amount
    totals_rows.append([
        Paragraph("Total Amount", styles['total_label']),
        Paragraph(fmt_currency(total_amount), styles['total_value']),
    ])

    # Discount coupon (if applicable)
    if discount_coupon:
        code = discount_coupon.get("code", "")
        disc_amt = discount_coupon.get("amount", 0)
        label = f"Discount Coupon"
        if code:
            label += f"  (<font color='#E53E3E'>{code}</font>)"
        totals_rows.append([
            Paragraph(label, styles['total_label']),
            Paragraph(f"- {fmt_currency(disc_amt)}", styles['discount_value']),
        ])

    # Grand total
    totals_rows.append([
        Paragraph("<b>Grand Total</b>", styles['total_label']),
        Paragraph(f"<b>{fmt_currency(grand_total)}</b>", styles['grand_total_value']),
    ])

    # Paid amount
    totals_rows.append([
        Paragraph("<b>Paid Amount</b>", styles['total_label']),
        Paragraph(f"<b>{fmt_currency(paid_amount)}</b>", styles['grand_total_value']),
    ])

    totals_table = Table(
        totals_rows,
        colWidths=[usable_w * 0.65, usable_w * 0.35],
    )
    totals_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5 * mm),
        ('LEFTPADDING', (0, 0), (0, -1), 2 * mm),
        ('RIGHTPADDING', (1, 0), (1, -1), 2 * mm),
        # Bottom border on grand total row
        ('LINEABOVE', (0, -2), (-1, -2), 0.75, TEAL_PRIMARY),
        ('LINEBELOW', (0, -1), (-1, -1), 0.75, TEAL_PRIMARY),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 3 * mm))

    # ── AMOUNT IN WORDS ───────────────────────────────────
    words = amount_in_words(grand_total)
    story.append(Paragraph(
        f'<i>Amount Chargeable (in words): <b>{words}</b></i>',
        styles['words']
    ))
    story.append(Spacer(1, 4 * mm))

    # ── PAYMENT MODE SUMMARY + PAN + LEGAL (kept together) ─
    tail_elements = []

    payment_info = data.get("payment_info")
    if payment_info:
        tail_elements.append(Paragraph("Payment Mode Summary", styles['heading']))
        pay_rows = [[
            Paragraph("MODE", styles['table_header']),
            Paragraph("REFERENCE", styles['table_header']),
            Paragraph("AMOUNT", styles['table_header']),
        ]]
        for pay in payment_info:
            pay_rows.append([
                Paragraph(pay.get("mode", ""), styles['table_cell']),
                Paragraph(pay.get("reference", ""), styles['table_cell']),
                Paragraph(fmt_currency(pay.get("amount", 0)), styles['table_cell_right']),
            ])
        pay_table = Table(pay_rows, colWidths=[usable_w * 0.3, usable_w * 0.42, usable_w * 0.28])
        pay_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), TEAL_PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 2.5 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2.5 * mm),
            ('GRID', (0, 0), (-1, -1), 0.3, MID_GRAY),
        ]))
        tail_elements.append(pay_table)
        tail_elements.append(Spacer(1, 4 * mm))

    pan_number = data.get("pan_number")
    if pan_number:
        tail_elements.append(Paragraph(
            f'Company PAN No. {pan_number}',
            styles['subtle']
        ))
        tail_elements.append(Spacer(1, 1.5 * mm))

    cheque_note = data.get("cheque_payable_to")
    if cheque_note:
        tail_elements.append(Paragraph(
            f'<i>Please make cheques in favor of "{cheque_note}"</i>',
            styles['subtle']
        ))

    divider_parts = "— · " * 12 + "—"
    tail_elements.append(Spacer(1, 5 * mm))
    tail_elements.append(Paragraph(
        f'<font color="#1A9E8F">{divider_parts}</font>',
        ParagraphStyle('divider', alignment=TA_CENTER, fontSize=8, leading=10)
    ))

    story.append(KeepTogether(tail_elements))

    # ── BUILD ─────────────────────────────────────────────
    doc.build(story, onFirstPage=template.on_page, onLaterPages=template.on_page)
    return output_path


# ══════════════════════════════════════════════════════════════
# SAMPLE INVOICE DATA — full parameter reference
# ══════════════════════════════════════════════════════════════
SAMPLE_INVOICE = {
    # ── Header & Meta ──
    "invoice_number": "NUC-2024-0042",          # Auto-generated or from Razorpay
    "invoice_date": "Apr 17, 2024",              # Same as date of transaction
    "order_number": "ORD-10563014628",           # Optional
    "sac_code": "999312",                        # Service Accounting Code

    # ── Company Details (Bill From) ──
    "company_name": "Nucleotide Healthcare Pvt Ltd",
    "company_address": "Bangalore, Karnataka, India",
    "gst_number": None,                          # Optional — shown if provided

    # ── Customer Details ──
    "customer_name": "Mohan Singh",
    "customer_address": "B-221, Divine Grace Omega-2, Greater Noida, UP - 201310",

    # ── Description (optional free text) ──
    "description": "Genetic One - Custom package for family",

    # ── Product-level items (simple mode) ──
    "items": [
        {"name": "Genetic One – Single",              "amount": 45000},
        {"name": "Genetic One – Custom (5 members)",   "amount": 225000},
        {"name": "Genetic One – Couple",               "amount": 90000},
    ],

    # ── Detailed per-person test items (Healthians-style) ──
    # Set to [] or omit to skip this section
    "detailed_items": [
        {
            "person_name": "Mohan Singh",
            "tests": [
                {"name": "Healthy India 2024 Full Body Checkup Signature", "amount": 5499},
                {"name": "Blood Group Profile ABO & Rh Typing (manual), Blood", "amount": 349},
            ],
        },
        {
            "person_name": "Usha Singh",
            "tests": [
                {"name": "Healthy India 2024 Full Body Checkup Signature", "amount": 5499},
                {"name": "Blood Group Profile ABO & Rh Typing (manual), Blood", "amount": 349},
            ],
        },
    ],

    # ── Totals ──
    "total_amount": 45000,
    "discount_coupon": {                          # Optional — omit or None to skip
        "code": "CC2500",
        "amount": 2500,
    },
    "grand_total": 42500,
    "paid_amount": 42500,

    # ── Payment Info (optional) ──
    "payment_info": [                             # Omit or None to skip section
        {"mode": "Razorpay", "reference": "pay_NxYzAbCdEfGh", "amount": 42500},
    ],

    # ── Subtle / Legal ──
    "pan_number": "AADCE5479M",                  # Shown in smaller lighter font
    "cheque_payable_to": "Nucleotide Healthcare Pvt Ltd",

    # ── Footer ──
    "customer_care_phone": "+91 9403891587",
    "customer_care_email": "info@nucleotide.life",
    "website": "www.nucleotide.life",
}


# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Generate a sample invoice for demonstration
    LOGO_PATH = "/mnt/user-data/uploads/1773369975308_image.png"
    OUTPUT = "/home/claude/sample_invoice.pdf"

    generate_invoice(SAMPLE_INVOICE, output_path=OUTPUT, logo_path=LOGO_PATH)
    print(f"✅ Invoice generated: {OUTPUT}")
