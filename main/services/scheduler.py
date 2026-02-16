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
from django.db import transaction
import random
from django.shortcuts import render
from main.models import TeachingAssignmentItem, Schedule, DayPeriod, TeacherAvailability

def generate_schedule(max_attempts=5):
    logs = []  # لیست لاگ‌ها

    for attempt in range(max_attempts):
        try:
            with transaction.atomic():

                Schedule.objects.all().delete()

                all_slots = list(
                    DayPeriod.objects.filter(day__is_active=True)
                    .select_related('day')
                )

                items = list(
                    TeachingAssignmentItem.objects.select_related(
                        'lesson', 'school_class', 'assignment__teacher'
                    ).order_by('-lesson__priority', '-weekly_hours')
                )

                random.shuffle(items)

                units = []
                for item in items:
                    for _ in range(item.weekly_hours):
                        units.append(item)

                random.shuffle(units)

                for unit in units:

                    best_slot = choose_best_slot(unit, all_slots)

                    if not best_slot:
                        # ذخیره لاگ بجای raise
                        logs.append(
                            f"⚠️ امکان چیدن درس {unit.lesson.name} برای کلاس {unit.school_class.name} وجود ندارد."
                        )
                        continue

                    Schedule.objects.create(
                        school_class=unit.school_class,
                        day_period=best_slot,
                        lesson=unit.lesson,
                        teacher=unit.assignment.teacher
                    )

                return logs  # برگشت لیست لاگ‌ها

        except Exception as e:
            logs.append(f"خطای جدی: {e}")
            continue

    return logs


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

    scored_slots.sort(reverse=True, key=lambda x: x[0])
    return scored_slots[0][1]


# =========================================
# بررسی معتبر بودن یک اسلات
# =========================================
def is_valid_slot(unit, slot):

    # کلاس آزاد باشد
    if Schedule.objects.filter(
        school_class=unit.school_class,
        day_period=slot
    ).exists():
        return False

    teacher = unit.assignment.teacher

    # اگر معلم ندارد (حالت بدون دبیر)
    if not teacher:
        return True

    # معلم آزاد باشد
    if Schedule.objects.filter(
        teacher=teacher,
        day_period=slot
    ).exists():
        return False

    # حضور معلم در آن روز
    availability = TeacherAvailability.objects.filter(
        teacher=teacher,
        day=slot.day
    ).first()

    if not availability:
        return False

    used_hours = Schedule.objects.filter(
        teacher=teacher,
        day_period__day=slot.day
    ).count()

    if used_hours >= availability.available_hours:
        return False

    # یک درس دوبار در یک روز تکرار نشود
    if Schedule.objects.filter(
        school_class=unit.school_class,
        lesson=unit.lesson,
        day_period__day=slot.day
    ).exists():
        return False

    return True


# =========================================
# امتیازدهی اسلات‌ها
# =========================================
def calculate_slot_score(unit, slot):
    score = 0

    score += unit.lesson.priority * 20
    score += max(0, 8 - slot.period_number)

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

    if previous_same_lesson and not two_before_same_lesson:
        score += 6

    if previous_same_lesson and two_before_same_lesson:
        score -= 8

    teacher = unit.assignment.teacher

    if teacher:
        teacher_before = Schedule.objects.filter(
            teacher=teacher,
            day_period__day=slot.day,
            day_period__period_number=slot.period_number - 1
        ).exists()

        teacher_after = Schedule.objects.filter(
            teacher=teacher,
            day_period__day=slot.day,
            day_period__period_number=slot.period_number + 1
        ).exists()

        if teacher_before or teacher_after:
            score += 10
        else:
            score -= 3

    return score
