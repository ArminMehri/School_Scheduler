import os
from io import BytesIO

from django.conf import settings

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _register_persian_font():
    """
    تلاش می‌کند فونت فارسی را رجیستر کند.
    مسیر پیشنهادی: static/fonts/Vazir.ttf
    اگر فونت نبود، از Helvetica استفاده می‌شود.
    """
    font_name = "Vazir"
    try:
        font_path = os.path.join(settings.BASE_DIR, "static", "fonts", "Vazir.ttf")
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            return font_name
    except Exception:
        pass
    return "Helvetica"


def _build_days_periods(days_qs):
    """
    days_qs: SchoolDay queryset with prefetch dayperiod_set
    خروجی: (days_list, day_periods_map, total_cols)
    """
    days = list(days_qs)
    day_periods = {}
    total_periods = 0
    for d in days:
        periods = list(d.dayperiod_set.all().order_by("period_number"))
        day_periods[d.id] = periods
        total_periods += len(periods)
    return days, day_periods, total_periods


def export_pdf_class_based(classes, days_qs, schedule_lookup):
    """
    schedule_lookup: dict[(class_id, period_id)] -> Schedule or None
    خروجی: bytes (pdf)
    """
    font_name = _register_persian_font()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=18,
        bottomMargin=18,
        title="برنامه کلاسی"
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "fa_title",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=14,
        leading=18,
        alignment=1,  # center
    )
    normal_style = ParagraphStyle(
        "fa_normal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=13,
        alignment=1,  # center
    )

    days, day_periods, total_periods = _build_days_periods(days_qs)

    elements = []

    # عرض ستون‌ها (یک ستون برای نام + بقیه برای زنگ‌ها)
    usable_width = doc.width
    col0 = 60  # ستون نام
    other = (usable_width - col0) / max(total_periods, 1)
    col_widths = [col0] + [other] * total_periods

    for idx, cls in enumerate(classes):
        elements.append(Paragraph(f"کلاس {cls.name} - پایه {cls.grade.name}", title_style))
        elements.append(Spacer(1, 8))

        # ---- ساخت جدول: 2 هدر + 1 ردیف داده
        # ردیف 0: روزها (merge)
        row0 = ["نام کلاس"]
        merges = []
        col = 1
        for d in days:
            periods = day_periods[d.id]
            cnt = len(periods)
            if cnt == 0:
                continue
            row0.append(d.name)
            # سلول‌های اضافی برای merge
            for _ in range(cnt - 1):
                row0.append("")
            if cnt > 1:
                merges.append(("SPAN", (col, 0), (col + cnt - 1, 0)))
            col += cnt

        # ردیف 1: زنگ‌ها
        row1 = [cls.name]
        for d in days:
            for p in day_periods[d.id]:
                row1.append(f"زنگ {p.period_number}")

        # ردیف 2: داده‌ها
        row2 = [""]
        for d in days:
            for p in day_periods[d.id]:
                sched = schedule_lookup.get((cls.id, p.id))
                if sched:
                    if sched.teacher:
                        txt = f"{sched.lesson.name}\n{sched.teacher.name}"
                    else:
                        txt = f"{sched.lesson.name}\nبدون دبیر"
                else:
                    txt = "---"
                row2.append(txt)

        data = [row0, row1, row2]

        table = Table(data, colWidths=col_widths, repeatRows=2)
        ts = TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.6, colors.grey),

            ("BACKGROUND", (0, 0), (-1, 1), colors.whitesmoke),
            ("FONTSIZE", (0, 0), (-1, 1), 10),

            # ستون اول ضخیم‌تر
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4F4F4")),
        ])

        # merge های روزها
        for m in merges:
            ts.add(*m)

        # رنگ قرمز برای "بدون دبیر"
        for c in range(1, 1 + total_periods):
            if "بدون دبیر" in (row2[c] or ""):
                ts.add("BACKGROUND", (c, 2), (c, 2), colors.red)
                ts.add("TEXTCOLOR", (c, 2), (c, 2), colors.white)
                ts.add("FONTSIZE", (c, 2), (c, 2), 9)

        table.setStyle(ts)
        elements.append(table)

        # صفحه بعدی
        if idx != len(classes) - 1:
            elements.append(PageBreak())

    doc.build(elements)
    return buffer.getvalue()


def export_pdf_teacher_based(teachers, days_qs, teacher_slot_lookup):
    """
    teacher_slot_lookup: dict[(teacher_id, period_id)] -> SchoolClass or None
    خروجی: bytes (pdf)
    """
    font_name = _register_persian_font()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=18,
        bottomMargin=18,
        title="برنامه دبیران"
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "fa_title",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=14,
        leading=18,
        alignment=1,
    )

    days, day_periods, total_periods = _build_days_periods(days_qs)

    elements = []
    elements.append(Paragraph("برنامه دبیران", title_style))
    elements.append(Spacer(1, 10))

    usable_width = doc.width
    col0 = 110  # نام دبیر
    other = (usable_width - col0) / max(total_periods, 1)
    col_widths = [col0] + [other] * total_periods

    # ردیف 0: روزها (merge)
    row0 = ["نام دبیر"]
    merges = []
    col = 1
    for d in days:
        periods = day_periods[d.id]
        cnt = len(periods)
        if cnt == 0:
            continue
        row0.append(d.name)
        for _ in range(cnt - 1):
            row0.append("")
        if cnt > 1:
            merges.append(("SPAN", (col, 0), (col + cnt - 1, 0)))
        col += cnt

    # ردیف 1: زنگ‌ها
    row1 = [""]
    for d in days:
        for p in day_periods[d.id]:
            row1.append(f"زنگ {p.period_number}")

    data = [row0, row1]

    # ردیف‌های دبیرها
    for t in teachers:
        r = [t.name]
        for d in days:
            for p in day_periods[d.id]:
                cls = teacher_slot_lookup.get((t.id, p.id))
                r.append(cls.name if cls else "---")
        data.append(r)

    table = Table(data, colWidths=col_widths, repeatRows=2)
    ts = TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.6, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 1), colors.whitesmoke),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4F4F4")),
        ("FONTSIZE", (0, 0), (-1, 1), 10),
    ])

    # merge روزها
    for m in merges:
        ts.add(*m)

    # خط ضخیم بین روزها مثل اکسل (آخر هر روز)
    # ستون‌های انتهایی روزها:
    end_cols = []
    c = 1
    for d in days:
        cnt = len(day_periods[d.id])
        if cnt:
            end_cols.append(c + cnt - 1)
            c += cnt
    for ec in end_cols:
        ts.add("LINEAFTER", (ec, 0), (ec, -1), 2, colors.black)

    table.setStyle(ts)
    elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
