from django.db import transaction
from django.db.models import Q
from main.models import (
    SchoolClass,
    Lesson,
    Teacher,
    TeachingAssignment,
    TeachingAssignmentItem,
)


def auto_assign_teachers():

    with transaction.atomic():

        # گرفتن سابقه قبلی قبل از حذف
        previous_assignments = {}

        for item in TeachingAssignmentItem.objects.select_related("assignment").all():
            previous_assignments[
                (item.school_class.id, item.lesson.id)
            ] = item.assignment.teacher.id

        # پاک کردن assignment قبلی
        TeachingAssignment.objects.all().delete()

        # ظرفیت باقی‌مانده هر معلم
        teacher_remaining = {
            teacher.id: teacher.weekly_capacity
            for teacher in Teacher.objects.all()
        }

        # برای هر کلاس
        for school_class in SchoolClass.objects.all():

            # فقط درس‌های مربوط به پایه کلاس
            lessons = Lesson.objects.filter(
                Q(for_all_grades=True) |
                Q(grades=school_class.grade)
            ).distinct()

            for lesson in lessons:

                required_hours = lesson.weekly_hours

                if required_hours <= 0:
                    continue

                # معلم‌هایی که این درس را می‌دهند
                possible_teachers = Teacher.objects.filter(
                    lessons=lesson
                )

                # فیلتر بر اساس محدودیت پایه
                filtered_teachers = []

                for teacher in possible_teachers:

                    if teacher.limit_to_grades:
                        if school_class.grade in teacher.grades.all():
                            filtered_teachers.append(teacher)
                    else:
                        filtered_teachers.append(teacher)

                # ❗ اگر هیچ معلمی نبود → رد شود (بدون ارور)
                if not filtered_teachers:
                    print(
                        f"⚠ هیچ معلمی برای {lesson.name} "
                        f"پایه {school_class.grade.name} یافت نشد."
                    )
                    continue

                # امتیازدهی
                def teacher_score(t):

                    score = teacher_remaining[t.id]

                    # اولویت با معلم قبلی همان کلاس
                    if previous_assignments.get(
                        (school_class.id, lesson.id)
                    ) == t.id:
                        score += 1000

                    return score

                filtered_teachers = sorted(
                    filtered_teachers,
                    key=teacher_score,
                    reverse=True
                )

                assigned = False

                for teacher in filtered_teachers:

                    if teacher_remaining[teacher.id] >= required_hours:

                        assignment, _ = TeachingAssignment.objects.get_or_create(
                            teacher=teacher
                        )

                        TeachingAssignmentItem.objects.create(
                            assignment=assignment,
                            school_class=school_class,
                            lesson=lesson,
                            weekly_hours=required_hours
                        )

                        teacher_remaining[teacher.id] -= required_hours
                        assigned = True
                        break

                # ❗ اگر ظرفیت کافی نبود → فقط رد شود
                if not assigned:
                    print(
                        f"⚠ ظرفیت کافی برای {lesson.name} "
                        f"در کلاس {school_class.name} وجود ندارد."
                    )
                    continue
