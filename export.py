"""
routers/export.py — CSV and PDF export generation
==================================================
Generates IRS-ready expense reports using:
  - pandas: data aggregation
  - ReportLab: PDF generation with tables
  - csv module: CSV export

Free tier: CSV only
Premium: PDF with summary + IRS Schedule C notes

Endpoints:
  GET /export/csv?month=YYYY-MM&year=YYYY
  GET /export/pdf?year=YYYY      (premium only)
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import io
import csv
import json
from datetime import datetime
import database
from routers.auth import verify_token

router = APIRouter()

@router.get("/csv")
def export_csv(
    month: Optional[str] = None,
    year: Optional[str] = None,
    deductible_only: bool = False,
    user_id: int = Depends(verify_token)
):
    """
    Export receipts as CSV.
    Free tier: available. Premium: adds deductible_type and state_notes columns.
    """
    conn = database.get_conn()
    user = conn.execute("SELECT is_premium FROM users WHERE id=?", (user_id,)).fetchone()

    query = "SELECT * FROM receipts WHERE user_id=?"
    params = [user_id]

    if month:
        query += " AND strftime('%Y-%m', receipt_date)=?"
        params.append(month)
    if year:
        query += " AND strftime('%Y', receipt_date)=?"
        params.append(year)
    if deductible_only:
        query += " AND is_deductible=1"

    query += " ORDER BY receipt_date DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    base_cols = ["Date", "Vendor", "Total", "Tax", "Category", "Subcategory"]
    premium_cols = ["Deductible", "Deductible Type", "Deductible %", "State Notes"]
    cols = base_cols + (premium_cols if user["is_premium"] else [])
    writer.writerow(cols)

    for r in rows:
        items = json.loads(database.decrypt(r["items_enc"])) if r["items_enc"] else []
        flags = json.loads(r["state_flags"]) if r["state_flags"] else {}
        row = [
            r["receipt_date"] or "",
            database.decrypt(r["vendor_enc"]) or "",
            f"{r['total']:.2f}" if r["total"] else "",
            f"{r['tax_amount']:.2f}" if r["tax_amount"] else "",
            r["category"] or "",
            r["subcategory"] or "",
        ]
        if user["is_premium"]:
            row += [
                "Yes" if r["is_deductible"] else "No",
                r["deductible_type"] or "",
                "",  # deductible_pct not stored per-receipt — add if needed
                flags.get("state_notes", "")
            ]
        writer.writerow(row)

    output.seek(0)
    filename = f"expenses_{month or year or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/pdf")
def export_pdf(
    year: Optional[str] = None,
    user_id: int = Depends(verify_token)
):
    """
    Premium only: Generate IRS-ready PDF expense report.
    Includes: summary table, deductibles, category breakdown, Schedule C notes.
    """
    conn = database.get_conn()
    user = conn.execute("SELECT is_premium, profile FROM users WHERE id=?", (user_id,)).fetchone()
    if not user["is_premium"]:
        conn.close()
        raise HTTPException(403, "PDF export requires Premium ($4.99/mo)")

    if not year:
        year = str(datetime.now().year)

    rows = conn.execute("""
        SELECT * FROM receipts
        WHERE user_id=? AND strftime('%Y', receipt_date)=?
        ORDER BY receipt_date DESC
    """, (user_id, year)).fetchall()
    conn.close()

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
    except ImportError:
        raise HTTPException(500, "PDF library not installed. Run: pip install reportlab")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph(f"Expense Report — {year}", styles["Title"]))
    elements.append(Spacer(1, 12))

    profile = json.loads(user["profile"]) if user["profile"] else {}
    state = profile.get("state", "US")
    elements.append(Paragraph(f"State: {state} | Generated: {datetime.now().strftime('%Y-%m-%d')}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Summary stats
    total_all = sum(r["total"] or 0 for r in rows)
    total_ded = sum(r["total"] or 0 for r in rows if r["is_deductible"])
    elements.append(Paragraph(f"<b>Total Expenses: ${total_all:.2f}</b>", styles["Normal"]))
    elements.append(Paragraph(f"<b>Total Deductible: ${total_ded:.2f}</b>", styles["Normal"]))
    elements.append(Paragraph(f"<b>Estimated Tax Savings (22%): ${total_ded*0.22:.2f}</b>", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Category breakdown table
    by_cat = {}
    for r in rows:
        cat = r["category"] or "Other"
        by_cat[cat] = by_cat.get(cat, 0.0) + (r["total"] or 0.0)

    cat_data = [["Category", "Total"]] + [[k, f"${v:.2f}"] for k, v in sorted(by_cat.items(), key=lambda x: -x[1])]
    cat_table = Table(cat_data, colWidths=[300, 100])
    cat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(Paragraph("<b>Category Breakdown</b>", styles["Heading2"]))
    elements.append(cat_table)
    elements.append(Spacer(1, 20))

    # Deductibles detail table
    ded_rows = [r for r in rows if r["is_deductible"]]
    if ded_rows:
        elements.append(Paragraph("<b>Deductible Expenses</b>", styles["Heading2"]))
        ded_data = [["Date", "Vendor", "Amount", "Type"]]
        for r in ded_rows:
            ded_data.append([
                r["receipt_date"] or "",
                database.decrypt(r["vendor_enc"]) or "",
                f"${r['total']:.2f}" if r["total"] else "",
                r["deductible_type"] or ""
            ])
        ded_table = Table(ded_data, colWidths=[80, 200, 80, 120])
        ded_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d6a4f")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#e8f5e9")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(ded_table)
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            "Note: Consult a tax professional before filing. Business meals are 50% deductible under IRS rules.",
            styles["Normal"]
        ))

    doc.build(elements)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=expenses_{year}.pdf"}
    )
