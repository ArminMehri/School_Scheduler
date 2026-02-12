from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from main.models import Schedule
from main.services.validator import run_full_validation
from main.services.scheduler import generate_schedule
from main.models import *
from django.http import HttpResponse
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement

from .models import SchoolClass, Schedule
import openpyxl
from openpyxl.styles import Alignment, Font
from django.http import HttpResponse
from .models import SchoolClass, SchoolDay, Schedule

def export_schedule_excel(request):
    # ایجاد Workbook و Sheet
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "برنامه کلاسی"

    # راست چین کردن همه سلول‌ها
    align_right = Alignment(horizontal='right', vertical='center', wrap_text=True)

    # فونت بولد برای عنوان‌ها
    bold_font = Font(bold=True)

    # گرفتن کلاس‌ها و روزها
    classes = SchoolClass.objects.select_related('grade').all()
    days = SchoolDay.objects.filter(is_active=True).prefetch_related('dayperiod_set')

    # محاسبه تعداد کل ستون‌ها
    total_periods = sum(day.dayperiod_set.count() for day in days)

    # ردیف اول: روزهای هفته
    col_index = 2  # ستون اول برای اسم کلاس
    for day in days:
        periods_count = day.dayperiod_set.count()
        cell = ws.cell(row=1, column=col_index, value=day.name)
        cell.alignment = align_right
        cell.font = bold_font

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
            cell.font = bold_font
            col_index += 1

    # ستون اول: اسم کلاس‌ها
    row_index = 3
    for school_class in classes:
        ws.cell(row=row_index, column=1, value=school_class.name).alignment = align_right

        col_index = 2
        for day in days:
            for period in day.dayperiod_set.all():
                sched = Schedule.objects.filter(
                    school_class=school_class,
                    day_period=period
                ).first()
                if sched:
                    text = f"{sched.lesson.name}\n{sched.teacher.name}"
                else:
                    text = "---"

                cell = ws.cell(row=row_index, column=col_index, value=text)
                cell.alignment = align_right
                col_index += 1

        row_index += 1

    # Auto width تقریبی برای ستون‌ها
    for col_cells in ws.columns:
        max_length = 0
        column_letter = None
        for cell in col_cells:
            # فقط سلول‌های واقعی (نه MergedCell) را در نظر بگیر
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

def export_schedule_word(request):
    document = Document()
    document.add_heading('برنامه کلاسی مدرسه', level=1)

    classes = SchoolClass.objects.select_related('grade').all()
    days = SchoolDay.objects.filter(is_active=True).prefetch_related('dayperiod_set')


    # محاسبه تعداد کل ستون‌ها
    total_periods = 0
    for day in days:
        total_periods += day.dayperiod_set.count()

    table = document.add_table(rows=2 + classes.count(), cols=1 + total_periods)
    table.style = 'Table Grid'

    # ردیف اول: روزهای هفته
    header_row_days = table.rows[0]
    header_row_days.cells[0].text = "کلاس"

    col_index = 1
    for day in days:
        periods = day.dayperiod_set.all()
        span_count = periods.count()

        header_row_days.cells[col_index].text = day.name

        if span_count > 1:
            for i in range(1, span_count):
                header_row_days.cells[col_index].merge(
                    header_row_days.cells[col_index + i]
                )

        col_index += span_count

    # ردیف دوم: زنگ‌ها
    header_row_periods = table.rows[1]
    header_row_periods.cells[0].text = ""

    col_index = 1
    for day in days:
        for period in day.dayperiod_set.all():
            header_row_periods.cells[col_index].text = f"زنگ {period.period_number}"
            col_index += 1

    # داده‌های کلاس‌ها
    row_index = 2
    for school_class in classes:
        row = table.rows[row_index]
        row.cells[0].text = f"{school_class.name}"

        col_index = 1

        for day in days:
            for period in day.dayperiod_set.all():
                sched = Schedule.objects.filter(
                    school_class=school_class,
                    day_period=period
                ).first()

                if sched:
                    row.cells[col_index].text = f"{sched.lesson.name}\n{sched.teacher.name}"
                else:
                    row.cells[col_index].text = "---"

                col_index += 1

        row_index += 1

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = 'attachment; filename=barname_kelasi.docx'
    document.save(response)

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
        generate_schedule()
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "errors": [str(e)]
        }, status=500)

    return JsonResponse({
        "status": "success",
        "message": "برنامه با موفقیت تولید شد"
    })
