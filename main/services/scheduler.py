from django.db import transaction
import random
from main.models import (
    TeachingAssignmentItem,
    Schedule,
    DayPeriod,
    TeacherAvailability,
    SchoolClass,
)


# =====================================================
# تابع اصلی با لاگ دقیق و جمع‌بندی
# =====================================================
def generate_schedule(max_attempts=50):
    logs = []

    all_slots = list(
        DayPeriod.objects.filter(day__is_active=True)
        .select_related("day")
        .order_by("day__id", "period_number")
    )

    if not all_slots:
        logs.append("[ERROR] هیچ زنگ فعالی تعریف نشده است.")
        return logs

    items = list(
        TeachingAssignmentItem.objects.select_related(
            "lesson", "school_class", "assignment__teacher"
        )
    )

    # بررسی تراز بودن ساعات هر کلاس و لاگ
    for school_class in SchoolClass.objects.all():
        total_slots = len(all_slots)
        total_hours = sum(
            i.weekly_hours for i in items if i.school_class == school_class
        )
        logs.append(f"[INFO] کلاس {school_class.name} - جمع ساعات: {total_hours}, تعداد زنگ‌ها: {total_slots}")

    # ساخت بلاک‌ها (۲تایی و تک‌زنگ)
    blocks = []
    for item in items:
        total = item.weekly_hours
        pair_count = total // 2
        single_count = total % 2

        for _ in range(pair_count):
            blocks.append({
                "item": item,
                "size": 2,
                "single": False
            })
        if single_count:
            blocks.append({
                "item": item,
                "size": 1,
                "single": True
            })

    # تلاش برای جایگذاری بلاک‌ها
    for attempt in range(max_attempts):
        temp = []
        random.shuffle(blocks)
        success = True
        logs.append(f"\n[ATTEMPT {attempt+1}] شروع تلاش برای جایگذاری بلاک‌ها")

        for block in blocks:
            item = block["item"]
            size = block["size"]
            is_single = block["single"]

            placed = False

            for i in range(len(all_slots) - size + 1):
                candidate = all_slots[i:i + size]

                # بلاک دو تایی باید پشت سر هم باشد
                if size == 2 and candidate[1].period_number != candidate[0].period_number + 1:
                    continue

                # کلاس آزاد باشد
                if any(s[0] == item.school_class and s[1] in candidate for s in temp):
                    continue

                # جلوگیری از افتادن ۴ ساعته‌ها در دو روز متوالی
                if item.weekly_hours >= 4:
                    previous_day = candidate[0].day.id - 1
                    if any(s[0] == item.school_class and s[2] == item.lesson and s[1].day.id == previous_day for s in temp):
                        continue

                # تک‌زنگ با paired درس چک شود
                if is_single:
                    paired = item.lesson.paired_lessons.all()
                    if paired.exists():
                        neighbor_ok = any(
                            s[0] == item.school_class
                            and s[2] in paired
                            and s[1].day == candidate[0].day
                            and abs(s[1].period_number - candidate[0].period_number) == 1
                            for s in temp
                        )
                        if not neighbor_ok:
                            continue
                    else:
                        if not item.lesson.allow_split:
                            continue

                # بررسی تداخل معلم
                teacher = item.assignment.teacher
                teacher_available = True
                if teacher:
                    for slot in candidate:
                        if any(s[3] == teacher and s[1] == slot for s in temp):
                            teacher_available = False
                            break

                # ثبت بلاک
                for slot in candidate:
                    assigned_teacher = None
                    if teacher and teacher_available:
                        availability = TeacherAvailability.objects.filter(
                            teacher=teacher, day=slot.day
                        ).first()
                        if availability:
                            used_hours = sum(
                                1 for s in temp if s[3] == teacher and s[1].day == slot.day
                            )
                            if used_hours < availability.available_hours:
                                assigned_teacher = teacher

                    temp.append((item.school_class, slot, item.lesson, assigned_teacher))
                    logs.append(f"[INFO] کلاس {item.school_class.name} - درس {item.lesson.name} ({'تک زنگ' if is_single else 'دو زنگ'}) در زنگ {slot.period_number} روز {slot.day.name} با معلم {assigned_teacher.name if assigned_teacher else 'None'} گذاشته شد.")

                placed = True
                break

            if not placed:
                success = False
                logs.append(f"[WARN] نتوانستیم درس {item.lesson.name} کلاس {item.school_class.name} جایگذاری کنیم!")

        # ذخیره جدول
        with transaction.atomic():
            Schedule.objects.all().delete()
            for school_class, slot, lesson, teacher in temp:
                Schedule.objects.create(
                    school_class=school_class,
                    day_period=slot,
                    lesson=lesson,
                    teacher=teacher
                )

        if success:
            logs.append("[SUCCESS] جدول برنامه با موفقیت ساخته شد.")
        else:
            logs.append("[INFO] تلاش انجام شد ولی بعضی درس‌ها یا معلم‌ها جایگذاری نشدند.")

        break  # حتی اگر کامل نشد، جدول ذخیره شود و لاگ داده شود

    # جمع‌بندی نهایی
    logs.append("\n[SUMMARY] جمع‌بندی آخر:")
    for school_class in SchoolClass.objects.all():
        scheduled_items = Schedule.objects.filter(school_class=school_class)
        total_slots = len(all_slots)
        scheduled_hours = scheduled_items.count()
        missing_hours = total_slots - scheduled_hours
        without_teacher = scheduled_items.filter(teacher=None).count()
        logs.append(f"[SUMMARY] کلاس {school_class.name}: {scheduled_hours}/{total_slots} زنگ پر شده، {without_teacher} درس بدون معلم، {missing_hours} زنگ خالی باقی مانده.")

    return logs
