from django.db import transaction
import random
from main.models import (
    TeachingAssignmentItem,
    Schedule,
    DayPeriod,
    TeacherAvailability,
)


# =========================================
# تابع اصلی تولید برنامه
# =========================================
def generate_schedule(max_attempts=5):

    for attempt in range(max_attempts):

        try:
            with transaction.atomic():

                Schedule.objects.all().delete()

                all_slots = list(
                    DayPeriod.objects.filter(day__is_active=True).select_related('day')
                )

                items = list(
                    TeachingAssignmentItem.objects.select_related(
                        'lesson', 'school_class', 'assignment'
                    ).order_by('-lesson__priority', '-weekly_hours')
                )

                # کمی shuffle برای جلوگیری از گیر تکراری
                random.shuffle(items)

                units = []
                for item in items:
                    for _ in range(item.weekly_hours):
                        units.append(item)

                random.shuffle(units)

                for unit in units:

                    best_slot = choose_best_slot(unit, all_slots)

                    if not best_slot:
                        raise Exception(
                            f"امکان چیدن درس {unit.lesson.name} "
                            f"برای کلاس {unit.school_class.name} وجود ندارد."
                        )

                    Schedule.objects.create(
                        school_class=unit.school_class,
                        teacher=unit.assignment.teacher,
                        lesson=unit.lesson,
                        day_period=best_slot
                    )

                # اگر اینجا رسید یعنی موفق بوده
                return

        except Exception as e:
            if attempt == max_attempts - 1:
                raise Exception(f"بعد از چند تلاش هنوز نشد: {e}")
            # دوباره تلاش می‌کند
            continue

# =========================================
# انتخاب بهترین اسلات
# =========================================
def choose_best_slot(unit, all_slots):
    scored_slots = []

    for slot in all_slots:
        if is_valid_slot(unit, slot):
            score = calculate_slot_score(unit, slot)
            scored_slots.append((score, slot))

    if not scored_slots:
        return None

    # مرتب‌سازی از بیشترین امتیاز
    scored_slots.sort(reverse=True, key=lambda x: x[0])

    # بهترین گزینه رو برگردون
    return scored_slots[0][1]


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
    availability = TeacherAvailability.objects.filter(
        teacher=unit.assignment.teacher,
        day=slot.day
    ).first()

    if not availability:
        return False

    # تعداد ساعت‌های گرفته شده در آن روز
    used_hours = Schedule.objects.filter(
        teacher=unit.assignment.teacher,
        day_period__day=slot.day
    ).count()

    if used_hours >= availability.available_hours:
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

    # 🔹 اولویت درس
    score += unit.lesson.priority * 20

    # 🔹 ترجیح زنگ‌های اول (ولی نه خیلی افراطی)
    score += max(0, 8 - slot.period_number)

    # ------------------------------
    # بررسی پشت سر هم بودن درس برای کلاس
    # ------------------------------

    previous_same_lesson = Schedule.objects.filter(
        school_class=unit.school_class,
        lesson=unit.lesson,
        day_period__day=slot.day,
        day_period__period_number=slot.period_number - 1
    ).exists()

    two_before_same_lesson = Schedule.objects.filter(
        school_class=unit.school_class,
        lesson=unit.lesson,
        day_period__day=slot.day,
        day_period__period_number=slot.period_number - 2
    ).exists()

    # اگر یک زنگ قبل همین بوده → تشویق ملایم
    if previous_same_lesson and not two_before_same_lesson:
        score += 6

    # اگر میشه سه تا پشت هم → کمی جریمه
    if previous_same_lesson and two_before_same_lesson:
        score -= 8

    # ------------------------------
    # جلوگیری از gap برای معلم
    # ------------------------------

    teacher_has_previous = Schedule.objects.filter(
        teacher=unit.assignment.teacher,
        day_period__day=slot.day,
        day_period__period_number=slot.period_number - 1
    ).exists()

    teacher_has_next = Schedule.objects.filter(
        teacher=unit.assignment.teacher,
        day_period__day=slot.day,
        day_period__period_number=slot.period_number + 1
    ).exists()

    if teacher_has_previous or teacher_has_next:
        score += 10  # تشویق قوی برای چسبیده بودن

    # اگر بین دو زنگ پر معلم بیفته (یعنی gap بسازه) → جریمه
    teacher_before = Schedule.objects.filter(
        teacher=unit.assignment.teacher,
        day_period__day=slot.day,
        day_period__period_number=slot.period_number - 1
    ).exists()

    teacher_after = Schedule.objects.filter(
        teacher=unit.assignment.teacher,
        day_period__day=slot.day,
        day_period__period_number=slot.period_number + 1
    ).exists()

    if not teacher_before and not teacher_after:
        score -= 3  # زنگ تک برای معلم

    return score


