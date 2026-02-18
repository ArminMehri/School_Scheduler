from ortools.sat.python import cp_model
from django.db import transaction
from main.models import (
    TeachingAssignmentItem,
    Schedule,
    DayPeriod,
)


def generate_schedule_with_ortools():

    model = cp_model.CpModel()

    # ===============================
    # گرفتن داده‌ها
    # ===============================

    slots = list(
        DayPeriod.objects.filter(day__is_active=True)
        .select_related("day")
        .order_by("day__id", "period_number")
    )

    items = list(
        TeachingAssignmentItem.objects.select_related(
            "lesson", "school_class", "assignment__teacher"
        )
    )

    if not slots:
        raise Exception("هیچ زنگ فعالی تعریف نشده است.")

    # ===============================
    # تعریف متغیرها
    # x[item, slot] = 1 اگر این درس در این زنگ باشد
    # ===============================

    x = {}

    for item in items:
        for slot in slots:
            x[(item.id, slot.id)] = model.NewBoolVar(
                f"x_item{item.id}_slot{slot.id}"
            )

    # ===============================
    # Constraint 1
    # هر کلاس در هر زنگ فقط یک درس
    # ===============================

    for slot in slots:
        for item in items:
            pass

        for school_class in set(i.school_class for i in items):

            model.Add(
                sum(
                    x[(item.id, slot.id)]
                    for item in items
                    if item.school_class == school_class
                ) == 1
            )

    # ===============================
    # Constraint 2
    # هر درس دقیقاً weekly_hours بار بیاید
    # ===============================

    for item in items:
        model.Add(
            sum(
                x[(item.id, slot.id)]
                for slot in slots
            ) == item.weekly_hours
        )

    # ===============================
    # Constraint 3
    # معلم همزمان دو کلاس نباشد
    # ===============================

    for slot in slots:
        teachers = set(
            item.assignment.teacher
            for item in items
            if item.assignment.teacher
        )

        for teacher in teachers:
            model.Add(
                sum(
                    x[(item.id, slot.id)]
                    for item in items
                    if item.assignment.teacher == teacher
                ) <= 1
            )

    # ===============================
    # حل مدل
    # ===============================

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30

    status = solver.Solve(model)

    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        raise Exception("هیچ جدول معتبری پیدا نشد.")

    # ===============================
    # ذخیره در دیتابیس
    # ===============================

    with transaction.atomic():

        Schedule.objects.all().delete()

        for item in items:
            for slot in slots:
                if solver.Value(x[(item.id, slot.id)]) == 1:

                    Schedule.objects.create(
                        school_class=item.school_class,
                        day_period=slot,
                        lesson=item.lesson,
                        teacher=item.assignment.teacher
                    )
