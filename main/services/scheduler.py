from django.db import transaction
from main.models import (
    TeachingAssignmentItem,
    Schedule,
    DayPeriod,
    TeacherAvailability,
)


# =========================================
# تابع اصلی تولید برنامه
# =========================================
def generate_schedule():

    with transaction.atomic():
        # پاک کردن برنامه قبلی
        Schedule.objects.all().delete()

        # گرفتن همه زنگ‌های فعال هفته
        all_slots = list(
            DayPeriod.objects.filter(day__is_active=True).select_related('day')
        )

        # گرفتن همه آیتم‌های اختصاص درس
        items = TeachingAssignmentItem.objects.select_related(
            'lesson', 'school_class', 'assignment'
        ).order_by('-lesson__priority', '-weekly_hours')

        HOURS_PER_SLOT = 2  # هر زنگ 2 ساعت کاری

        units = []
        for item in items:
            needed_slots = -(-item.weekly_hours // HOURS_PER_SLOT)  # گرد کردن به بالا
            for _ in range(needed_slots):
                units.append(item)

        # شروع چیدن واحدها
        for unit in units:
            best_slot = choose_best_slot(unit, all_slots)

            if not best_slot:
                # 🔹 دیباگ دقیق قبل از ارور
                valid_slots = []
                invalid_slots = []
                for slot in all_slots:
                    if is_valid_slot(unit, slot):
                        valid_slots.append(f"{slot.day.name} - زنگ {slot.period_number}")
                    else:
                        reason = get_invalid_reason(unit, slot)
                        invalid_slots.append(f"{slot.day.name} - زنگ {slot.period_number} ({reason})")

                debug_msg = (
                    f"\n❌ خطا در چیدن درس '{unit.lesson.name}' برای کلاس '{unit.school_class.name}'"
                    f"\nمعلم: {unit.assignment.teacher.name}"
                    f"\nتعداد کل اسلات‌ها: {len(all_slots)}"
                    f"\nاسلات‌های معتبر: {valid_slots}"
                    f"\nاسلات‌های نامعتبر: {invalid_slots}\n"
                )
                print(debug_msg)

                raise Exception(
                    f"امکان چیدن درس {unit.lesson.name} "
                    f"برای کلاس {unit.school_class.name} وجود ندارد."
                )

            # ایجاد رکورد در Schedule
            Schedule.objects.create(
                school_class=unit.school_class,
                teacher=unit.assignment.teacher,
                lesson=unit.lesson,
                day_period=best_slot
            )


# =========================================
# انتخاب بهترین اسلات
# =========================================
def choose_best_slot(unit, all_slots):
    best_slot = None
    best_score = -1
    for slot in all_slots:
        if not is_valid_slot(unit, slot):
            continue
        score = calculate_slot_score(unit, slot)
        if score > best_score:
            best_score = score
            best_slot = slot
    return best_slot


# =========================================
# بررسی معتبر بودن یک اسلات
# =========================================
def is_valid_slot(unit, slot):
    # کلاس در این زنگ آزاد باشد
    if Schedule.objects.filter(school_class=unit.school_class, day_period=slot).exists():
        return False

    # معلم در این زنگ آزاد باشد
    if Schedule.objects.filter(teacher=unit.assignment.teacher, day_period=slot).exists():
        return False

    # معلم در این زنگ حضور داشته باشد
    if not TeacherAvailability.objects.filter(
        teacher=unit.assignment.teacher,
        day_periods=slot,
        day_periods__day__is_active=True
    ).exists():
        return False

    # ✅ شرط جدید: یک درس نباید دوبار در یک روز تکرار شود
    if Schedule.objects.filter(
        school_class=unit.school_class,
        lesson=unit.lesson,
        day_period__day=slot.day
    ).exists():
        return False

    return True


# =========================================
# دلیل نامعتبر بودن یک اسلات (برای دیباگ)
# =========================================
def get_invalid_reason(unit, slot):
    if Schedule.objects.filter(school_class=unit.school_class, day_period=slot).exists():
        return "کلاس در این زنگ پر است"
    if Schedule.objects.filter(teacher=unit.assignment.teacher, day_period=slot).exists():
        return "معلم در این زنگ پر است"
    if not TeacherAvailability.objects.filter(
        teacher=unit.assignment.teacher,
        day_periods=slot,
        day_periods__day__is_active=True
    ).exists():
        return "معلم در این زنگ حضور ندارد"
    return "نامشخص"


# =========================================
# سیستم امتیازدهی اسلات‌ها
# =========================================
def calculate_slot_score(unit, slot):
    score = 0
    # تاثیر اولویت درس
    score += unit.lesson.priority * 20
    # ترجیح زنگ‌های اول
    score += max(0, 10 - slot.period_number)
    # جلوگیری از پشت سر هم افتادن یک درس
    previous_same_lesson = Schedule.objects.filter(
        school_class=unit.school_class,
        lesson=unit.lesson,
        day_period__day=slot.day,
        day_period__period_number=slot.period_number - 1
    ).exists()
    if previous_same_lesson:
        score -= 5
    return score
