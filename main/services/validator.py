from django.db import models
from main.models import (
    SchoolClass,
    TeachingAssignment,
    Teacher,
    TeacherAvailability,
    Lesson,
    SchoolDay,
    DayPeriod,
)


# =========================================
# ظرفیت کل زنگ‌های فعال هفته
# =========================================

def get_total_weekly_slots():
    return DayPeriod.objects.filter(
        day__is_active=True
    ).count()


# =========================================
# 1️⃣ بررسی ظرفیت هر کلاس
# =========================================

def validate_class_capacity():
    errors = []

    total_slots = get_total_weekly_slots()

    for school_class in SchoolClass.objects.all():

        assignments = TeachingAssignment.objects.filter(
            school_class=school_class
        ).select_related('lesson')

        total_hours = sum(a.lesson.weekly_hours for a in assignments)

        if total_hours > total_slots:
            errors.append(
                f"کلاس {school_class.name} بیشتر از ظرفیت هفته ساعت دارد. "
                f"({total_hours} > {total_slots})"
            )

    return errors


# =========================================
# 2️⃣ بررسی ظرفیت هفتگی هر دبیر
# =========================================

def validate_teacher_capacity():
    errors = []

    for teacher in Teacher.objects.all():

        assignments = TeachingAssignment.objects.filter(
            teacher=teacher
        ).select_related('lesson')

        total_hours = sum(a.lesson.weekly_hours for a in assignments)

        if total_hours > teacher.weekly_capacity:
            errors.append(
                f"دبیر {teacher.name} بیشتر از ظرفیت هفتگی‌اش درس دارد. "
                f"({total_hours} > {teacher.weekly_capacity})"
            )

    return errors


# =========================================
# 3️⃣ بررسی حضور واقعی دبیر در زنگ‌ها
# =========================================

def validate_teacher_availability():
    errors = []

    for teacher in Teacher.objects.all():

        available_slots = TeacherAvailability.objects.filter(
            teacher=teacher,
            day_period__day__is_active=True
        ).count()

        assigned_hours = sum(
            a.lesson.weekly_hours
            for a in TeachingAssignment.objects.filter(
                teacher=teacher
            ).select_related('lesson')
        )

        if assigned_hours > available_slots:
            errors.append(
                f"دبیر {teacher.name} به اندازه کافی زنگ حضور ندارد. "
                f"({assigned_hours} > {available_slots})"
            )

    return errors


# =========================================
# 4️⃣ بررسی تعطیل نبودن روزهایی که زنگ دارند
# =========================================

def validate_days():
    errors = []

    inactive_days = SchoolDay.objects.filter(is_active=False)

    for day in inactive_days:
        if DayPeriod.objects.filter(day=day).exists():
            errors.append(
                f"روز {day.name} تعطیل است ولی زنگ برای آن ثبت شده."
            )

    return errors


# =========================================
# 5️⃣ بررسی تخصیص یکتای درس برای هر کلاس
# =========================================

def validate_unique_assignment():
    errors = []

    duplicates = (
        TeachingAssignment.objects
        .values('school_class', 'lesson')
        .annotate(count=models.Count('id'))
        .filter(count__gt=1)
    )

    for d in duplicates:
        errors.append(
            "یک درس برای یک کلاس بیش از یک دبیر دارد."
        )

    return errors


# =========================================
# 6️⃣ بررسی امکان جفت شدن درس‌های با ساعت فرد
# =========================================

def validate_odd_lessons():
    errors = []

    odd_count = 0

    assignments = TeachingAssignment.objects.select_related('lesson')

    for a in assignments:
        if a.lesson.weekly_hours % 2 == 1:
            odd_count += 1

    if odd_count % 2 != 0:
        errors.append(
            "تعداد درس‌های با ساعت فرد قابل جفت شدن نیست."
        )

    return errors


# =========================================
# اجرای کامل همه اعتبارسنجی‌ها
# =========================================

def run_full_validation():
    errors = []

    errors += validate_class_capacity()
    errors += validate_teacher_capacity()
    errors += validate_teacher_availability()
    errors += validate_days()
    errors += validate_unique_assignment()
    errors += validate_odd_lessons()

    return errors
