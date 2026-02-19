from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from main.models import Schedule
from main.services.validator import run_full_validation
from main.models import *
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from .solver_engine import generate_schedule_with_ortools
from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill,Border,Side
from django.http import HttpResponse
from main.models import SchoolClass, SchoolDay, Schedule
from openpyxl.worksheet.page import PageMargins
from main.services.pdf_export import *
import arabic_reshaper
from bidi.algorithm import get_display
from django.http import HttpResponse
from django.conf import settings
from django.utils import timezone
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.contrib.staticfiles import finders
import os
from .models import SchoolClass, SchoolDay, Schedule


def fa(text: str) -> str:
    if text is None:
        text = ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def export_schedule_pdf(request):
    # ✅ پیدا کردن فونت از static
    vazir_path = finders.find("fonts/Vazir.ttf")
    vazir_bold_path = finders.find("fonts/Vazir-Bold.ttf")

    if not vazir_path or not vazir_bold_path:
        raise Exception("فونت Vazir داخل static پیدا نشد. مسیر درست: main/static/fonts/")

    pdfmetrics.registerFont(TTFont("Vazir", vazir_path))
    pdfmetrics.registerFont(TTFont("VazirBold", vazir_bold_path))

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="barname_kelasi.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=18,
        bottomMargin=18,
    )

    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "base",
        parent=styles["Normal"],
        fontName="Vazir",
        fontSize=9,
        leading=11,
        alignment=2,
    )
    title_style = ParagraphStyle(
        "title",
        parent=styles["Title"],
        fontName="VazirBold",
        fontSize=14,
        alignment=2,
    )

    classes = SchoolClass.objects.select_related("grade").all()
    days = SchoolDay.objects.filter(is_active=True).prefetch_related("dayperiod_set")

    story = []
    story.append(Paragraph(fa("برنامه کلاسی مدرسه"), title_style))
    story.append(Spacer(1, 8))

    for idx, school_class in enumerate(classes):
        story.append(Paragraph(
            fa(f"کلاس {school_class.name} - پایه {school_class.grade.name}"),
            ParagraphStyle("cls", parent=base, fontName="VazirBold", fontSize=11)
        ))
        story.append(Spacer(1, 6))

        header_row1 = [fa("کلاس")]
        header_row2 = [""]

        day_periods = []
        total_cols = 1
        for day in days:
            periods = list(day.dayperiod_set.all())
            day_periods.append((day, periods))
            total_cols += len(periods)
            header_row1 += [fa(day.name)] + [""] * (len(periods) - 1)
            header_row2 += [fa(f"زنگ {p.period_number}") for p in periods]

        row = [fa(school_class.name)]
        for day, periods in day_periods:
            for period in periods:
                sched = Schedule.objects.filter(
                    school_class=school_class,
                    day_period=period
                ).select_related("lesson", "teacher").first()

                if sched:
                    if sched.teacher:
                        txt = f"{sched.lesson.name}\n{sched.teacher.name}"
                    else:
                        txt = f"{sched.lesson.name}\nبدون معلم"
                else:
                    txt = "---"

                row.append(fa(txt))

        data = [header_row1, header_row2, row]

        col_widths = [70] + [(doc.width - 70) / (total_cols - 1)] * (total_cols - 1)
        table = Table(data, colWidths=col_widths, repeatRows=2)

        ts = TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Vazir"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#EDEDED")),
            ("FONTNAME", (0, 0), (-1, 1), "VazirBold"),
        ])

        col = 1
        for day, periods in day_periods:
            if len(periods) > 1:
                ts.add("SPAN", (col, 0), (col + len(periods) - 1, 0))
            col += len(periods)

        for c in range(1, total_cols):
            if "بدون معلم" in data[2][c]:
                ts.add("BACKGROUND", (c, 2), (c, 2), colors.red)
                ts.add("TEXTCOLOR", (c, 2), (c, 2), colors.white)
                ts.add("FONTNAME", (c, 2), (c, 2), "VazirBold")

        table.setStyle(ts)
        story.append(table)

        if idx != len(classes) - 1:
            story.append(PageBreak())

    doc.build(story)
    return response

def export_schedule_excel(request):
    # ایجاد Workbook و Sheet
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "برنامه کلاسی"

    # تنظیم راست‌چین و فونت B Titr
    align_right = Alignment(horizontal='right', vertical='center', wrap_text=True)
    b_titr_font = Font(name='B Titr')

    # ✅ استایل قرمز برای سلول‌های بدون معلم
    red_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    white_bold_font = Font(name='B Titr', color="FFFFFF", bold=True)

    # گرفتن کلاس‌ها و روزها
    classes = SchoolClass.objects.select_related('grade').all()
    days = SchoolDay.objects.filter(is_active=True).prefetch_related('dayperiod_set')

    # ردیف اول: روزهای هفته
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
    cell = ws.cell(row=1, column=1, value="نام کلاس")
    cell.alignment = align_right
    cell.font = Font(name='B Titr')

    col_index = 2  # ستون اول برای اسم کلاس
    for day in days:
        periods_count = day.dayperiod_set.count()
        cell = ws.cell(row=1, column=col_index, value=day.name)
        cell.alignment = align_right
        cell.font = b_titr_font

        if periods_count > 1:
            ws.merge_cells(
                start_row=1, start_column=col_index,
                end_row=1, end_column=col_index + periods_count - 1
            )

        col_index += periods_count

    # ردیف دوم: زنگ‌ها
    col_index = 2
    for day in days:
        for period in day.dayperiod_set.all():
            cell = ws.cell(row=2, column=col_index, value=f"زنگ {period.period_number}")
            cell.alignment = align_right
            cell.font = b_titr_font
            col_index += 1

    # ستون اول: اسم کلاس‌ها
    row_index = 3
    for school_class in classes:
        cell_class = ws.cell(row=row_index, column=1, value=school_class.name)
        cell_class.alignment = align_right
        cell_class.font = b_titr_font

        col_index = 2
        for day in days:
            for period in day.dayperiod_set.all():
                sched = Schedule.objects.filter(
                    school_class=school_class,
                    day_period=period
                ).first()

                cell = ws.cell(row=row_index, column=col_index)

                if sched:
                    if sched.teacher:
                        cell.value = f"{sched.lesson.name}\n{sched.teacher.name}"
                        cell.font = b_titr_font
                    else:
                        cell.value = f"{sched.lesson.name}\nبدون معلم"
                        cell.fill = red_fill
                        cell.font = white_bold_font
                else:
                    cell.value = "---"
                    cell.font = b_titr_font

                cell.alignment = align_right
                col_index += 1

        row_index += 1

    # تنظیم عرض ستون‌ها (Auto width تقریبی)
    for col_cells in ws.columns:
        max_length = 0
        column_letter = None
        for cell in col_cells:
            if hasattr(cell, "column_letter") and cell.value:
                max_length = max(max_length, len(str(cell.value)))
                if column_letter is None:
                    column_letter = cell.column_letter
        if column_letter:
            ws.column_dimensions[column_letter].width = max_length + 5

    # پاسخ HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=barname_kelasi.xlsx'
    wb.save(response)
    return response

def export_schedule_excel_teacher(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "برنامه دبیران"

    # ------------------------
    # استایل‌ها
    # ------------------------
    align_right = Alignment(horizontal='right', vertical='center', wrap_text=True)
    align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)

    b_titr = Font(name='B Titr')
    b_titr_bold = Font(name='B Titr', bold=True)

    header_fill = PatternFill(start_color="EDEDED", end_color="EDEDED", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    thick_right_border = Border(
        right=Side(style="thick")
    )

    thick_left_border = Border(
        left=Side(style="thick")
    )

    # ------------------------
    # تنظیمات پرینت
    # ------------------------
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = 9  # A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    ws.page_margins = PageMargins(
        left=0.2, right=0.2,
        top=0.3, bottom=0.3,
        header=0.1, footer=0.1
    )

    ws.print_title_rows = "1:2"

    # ------------------------
    teachers = Teacher.objects.all().order_by("name")
    days = SchoolDay.objects.filter(is_active=True).prefetch_related('dayperiod_set')

    # ------------------------
    # هدر
    # ------------------------
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
    c = ws.cell(row=1, column=1, value="نام دبیر")
    c.alignment = align_center
    c.font = b_titr_bold
    c.fill = header_fill
    c.border = thick_left_border

    col_index = 2
    day_end_columns = []

    for day in days:
        periods = day.dayperiod_set.all()
        start_col = col_index
        end_col = col_index + periods.count() - 1
        day_end_columns.append(end_col)

        c = ws.cell(row=1, column=start_col, value=day.name)
        c.alignment = align_center
        c.font = b_titr_bold
        c.fill = header_fill

        if periods.count() > 1:
            ws.merge_cells(
                start_row=1, start_column=start_col,
                end_row=1, end_column=end_col
            )

        col_index += periods.count()

    # ------------------------
    # ردیف دوم: زنگ‌ها
    # ------------------------
    col_index = 2
    for day in days:
        for period in day.dayperiod_set.all():
            c = ws.cell(row=2, column=col_index, value=f"زنگ {period.period_number}")
            c.alignment = align_center
            c.font = b_titr_bold
            c.fill = header_fill
            c.border = thin_border
            col_index += 1

    # ------------------------
    # داده‌ها
    # ------------------------
    row_index = 3
    for teacher in teachers:
        c0 = ws.cell(row=row_index, column=1, value=teacher.name)
        c0.alignment = align_right
        c0.font = b_titr_bold
        c0.border = thick_left_border

        col_index = 2
        for day in days:
            for period in day.dayperiod_set.all():
                sched = Schedule.objects.filter(
                    teacher=teacher,
                    day_period=period
                ).select_related("school_class").first()

                cell = ws.cell(row=row_index, column=col_index)
                cell.alignment = align_center
                cell.font = b_titr
                cell.value = sched.school_class.name if sched else "---"
                cell.border = thin_border

                col_index += 1

        row_index += 1

    # ------------------------
    # 🔥 خط ضخیم بین روزها
    # ------------------------
    max_row = ws.max_row
    for end_col in day_end_columns:
        for r in range(1, max_row + 1):
            ws.cell(row=r, column=end_col).border = Border(
                right=Side(style="thick"),
                left=ws.cell(row=r, column=end_col).border.left,
                top=ws.cell(row=r, column=end_col).border.top,
                bottom=ws.cell(row=r, column=end_col).border.bottom,
            )

    # ------------------------
    # Auto width + row height
    # ------------------------
    for col_cells in ws.columns:
        max_length = 0
        column_letter = None
        for cell in col_cells:
            if hasattr(cell, "column_letter") and cell.value:
                max_length = max(max_length, len(str(cell.value)))
                if column_letter is None:
                    column_letter = cell.column_letter
        if column_letter:
            ws.column_dimensions[column_letter].width = min(max_length + 4, 28)

    for r in range(1, ws.max_row + 1):
        ws.row_dimensions[r].height = 28

    # ------------------------
    # Print Area
    # ------------------------
    last_col = ws.max_column
    last_row = ws.max_row
    ws.print_area = f"A1:{openpyxl.utils.get_column_letter(last_col)}{last_row}"

    # ------------------------
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=barname_dabiran.xlsx'
    wb.save(response)
    return response

def schedule_table(request):

    classes = SchoolClass.objects.select_related('grade').all()
    days = SchoolDay.objects.filter(is_active=True).prefetch_related('dayperiod_set')

    schedules = Schedule.objects.select_related(
        'school_class',
        'teacher',
        'lesson',
        'day_period',
        'day_period__day'
    )

    data_table = {}

    for schedule in schedules:
        class_id = schedule.school_class.id
        day_id = schedule.day_period.day.id
        period_id = schedule.day_period.id

        data_table.setdefault(class_id, {})
        data_table[class_id].setdefault(day_id, {})
        data_table[class_id][day_id][period_id] = schedule

    context = {
        "classes": classes,
        "days": days,
        "data_table": data_table
    }

    return render(request, "schedule_table.html", context)


@require_POST
def build_schedule(request):
    # اجرای اعتبارسنجی قبل از تولید برنامه
    errors = run_full_validation()

    if errors:
        return JsonResponse({
            "status": "error",
            "errors": errors
        }, status=400)

    try:
        generate_schedule_with_ortools()
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "errors": [str(e)]
        }, status=500)

    return JsonResponse({
        "status": "success",
        "message": "برنامه با موفقیت تولید شد"
    })

def schedule_build_view(request):
    if request.method == "POST" and "clear_logs" in request.POST:
        # پاک کردن لاگ‌ها
        request.session['schedule_logs'] = []
        return redirect('schedule-build')

    if request.method == "POST" and "generate_schedule" in request.POST:
        generate_schedule_with_ortools()
        request.session['schedule_logs'] = ["برنامه با موتور حرفه‌ای ساخته شد."]
        request.session['schedule_logs'] = logs
        return redirect('schedule-build')

    # دریافت لاگ‌ها از session
    logs = request.session.get('schedule_logs', [])
    return render(request, "schedule_logs.html", {"logs": logs})



