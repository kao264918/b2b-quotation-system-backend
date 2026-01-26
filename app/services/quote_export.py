"""
Quote Export Service - PDF and Excel generation for quotes
"""
from io import BytesIO
from typing import Optional
from decimal import Decimal

from app.models.quote import Quote


def generate_quote_pdf(quote: Quote, version: Optional[int] = None) -> bytes:
    """
    Generate a PDF for the given quote.
    Uses ReportLab for PDF generation with Traditional Chinese support.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    
    # Try to register a Chinese font (fallback to default if not available)
    try:
        pdfmetrics.registerFont(TTFont('NotoSansTC', '/System/Library/Fonts/PingFang.ttc'))
        chinese_font = 'NotoSansTC'
    except:
        chinese_font = 'Helvetica'
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', 
        parent=styles['Title'],
        fontName=chinese_font,
        fontSize=18,
        spaceAfter=12
    )
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontName=chinese_font,
        fontSize=10
    )
    
    elements = []
    
    # Header
    ver = version or quote.version
    elements.append(Paragraph(f"報價單 {quote.quote_number} v{ver}", title_style))
    elements.append(Spacer(1, 12))
    
    # Quote Info
    elements.append(Paragraph(f"<b>標題：</b>{quote.title}", normal_style))
    elements.append(Paragraph(f"<b>狀態：</b>{get_status_label(quote.status)}", normal_style))
    if quote.accounting_status:
        elements.append(Paragraph(f"<b>會計狀態：</b>{get_accounting_status_label(quote.accounting_status)}", normal_style))
    if quote.valid_until:
        elements.append(Paragraph(f"<b>有效期限：</b>{quote.valid_until.strftime('%Y-%m-%d')}", normal_style))
    elements.append(Spacer(1, 12))
    
    # Customer Info
    if quote.customer:
        elements.append(Paragraph("<b>客戶資訊</b>", normal_style))
        elements.append(Paragraph(f"公司：{quote.customer.company_name}", normal_style))
        if hasattr(quote.customer, 'tax_id') and quote.customer.tax_id:
            elements.append(Paragraph(f"統編：{quote.customer.tax_id}", normal_style))
        elements.append(Spacer(1, 12))
    
    # Items Table
    if quote.items:
        elements.append(Paragraph("<b>報價明細</b>", normal_style))
        elements.append(Spacer(1, 6))
        
        table_data = [['項目名稱', '單位', '數量', '單價', '小計']]
        for item in quote.items:
            table_data.append([
                item.name,
                item.unit,
                str(item.quantity),
                f"${item.unit_price:,.2f}",
                f"${item.subtotal:,.2f}"
            ])
        
        table = Table(table_data, colWidths=[150, 40, 50, 70, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), chinese_font),
            ('FONTNAME', (0, 1), (-1, -1), chinese_font),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))
    
    # Totals
    elements.append(Paragraph(f"<b>未稅小計：</b> ${quote.subtotal:,.2f}", normal_style))
    elements.append(Paragraph(f"<b>稅額：</b> ${quote.tax_total:,.2f}", normal_style))
    elements.append(Paragraph(f"<b>總計：</b> ${quote.total:,.2f}", normal_style))
    
    # Notes
    if quote.notes:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("<b>備註：</b>", normal_style))
        elements.append(Paragraph(quote.notes, normal_style))
    
    doc.build(elements)
    return buffer.getvalue()


def generate_quote_excel(quote: Quote, version: Optional[int] = None) -> bytes:
    """
    Generate an Excel file for the given quote.
    Uses openpyxl for Excel generation.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Border, Side, Alignment
    
    wb = Workbook()
    ws = wb.active
    ws.title = "報價單"
    
    ver = version or quote.version
    
    # Header
    ws['A1'] = f"報價單 {quote.quote_number} v{ver}"
    ws['A1'].font = Font(size=16, bold=True)
    ws.merge_cells('A1:E1')
    
    # Quote Info
    ws['A3'] = "標題"
    ws['B3'] = quote.title
    ws['A4'] = "狀態"
    ws['B4'] = get_status_label(quote.status)
    ws['A5'] = "會計狀態"
    ws['B5'] = get_accounting_status_label(quote.accounting_status) if quote.accounting_status else "-"
    ws['A6'] = "有效期限"
    ws['B6'] = quote.valid_until.strftime('%Y-%m-%d') if quote.valid_until else "-"
    
    # Customer Info
    if quote.customer:
        ws['A8'] = "客戶"
        ws['A8'].font = Font(bold=True)
        ws['A9'] = "公司"
        ws['B9'] = quote.customer.company_name
        start_row = 11
    else:
        start_row = 8
    
    # Items Header
    ws[f'A{start_row}'] = "報價明細"
    ws[f'A{start_row}'].font = Font(bold=True)
    start_row += 1
    
    headers = ['項目名稱', '單位', '數量', '單價', '小計']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=col, value=header)
        cell.font = Font(bold=True)
        cell.border = Border(bottom=Side(style='thin'))
    
    # Items Data
    for idx, item in enumerate(quote.items):
        row = start_row + idx + 1
        ws.cell(row=row, column=1, value=item.name)
        ws.cell(row=row, column=2, value=item.unit)
        ws.cell(row=row, column=3, value=float(item.quantity))
        ws.cell(row=row, column=4, value=float(item.unit_price))
        ws.cell(row=row, column=5, value=float(item.subtotal))
        ws.cell(row=row, column=5).number_format = '#,##0.00'
    
    # Totals
    totals_row = start_row + len(quote.items) + 2
    ws[f'D{totals_row}'] = "未稅小計"
    ws[f'E{totals_row}'] = float(quote.subtotal)
    ws[f'E{totals_row}'].number_format = '#,##0.00'
    
    ws[f'D{totals_row + 1}'] = "稅額"
    ws[f'E{totals_row + 1}'] = float(quote.tax_total)
    ws[f'E{totals_row + 1}'].number_format = '#,##0.00'
    
    ws[f'D{totals_row + 2}'] = "總計"
    ws[f'E{totals_row + 2}'] = float(quote.total)
    ws[f'E{totals_row + 2}'].font = Font(bold=True)
    ws[f'E{totals_row + 2}'].number_format = '#,##0.00'
    
    # Column widths
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 15
    
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def get_status_label(status: str) -> str:
    """Get Chinese label for quotation status."""
    labels = {
        "draft": "草稿",
        "confirmed": "已建立",
        "closed": "結案",
        "discarded": "作廢"
    }
    return labels.get(status, status)


def get_accounting_status_label(status: str) -> str:
    """Get Chinese label for accounting status."""
    labels = {
        "unpaid": "未付款",
        "paid": "已付款"
    }
    return labels.get(status, status)
