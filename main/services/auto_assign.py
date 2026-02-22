from django.db import transaction
from django.db.models import Q

from main.models import (
    School,
    SchoolClass,
    Lesson,
    Teacher,
    TeachingAssignment,
    TeachingAssignmentItem,
)


NO_TEACHER_NAME = "بدون دبیر (سیستمی)"


def _pick_default_school_if_possible():
    # برای اینکه پروژه‌های تک‌مدرسه‌ای مثل قبل نشکنند
    qs = School.objects.all()
    if qs.count() == 1:
        return qs.first()
    return None


def get_no_teacher(school=None):
    """
    فقط برای درس‌هایی که allow_without_teacher=True هست.
    چون TeachingAssignmentItem حتماً assignment می‌خواهد و assignment هم teacher می‌خواهد،
    مجبوریم یک Teacher سیستمی داشته باشیم (برای همان مدرسه).
    """
    if hasattr(Teacher, "school"):
        if school is None:
            school = _pick_default_school_if_possible()
        if school is None:
            raise Exception("School مشخص نیست. get_no_teacher(school=...) را صدا بزنید.")

        t, _ = Teacher.objects.get_or_create(
            school=school,
            name=NO_TEACHER_NAME,
            defaults={
                "weekly_capacity": 10**9,
                "limit_to_grades": False,
            }
        )
        return t

    # fallback (اگر پروژه قدیمی بود و school نداشت)
    t, _ = Teacher.objects.get_or_create(
        name=NO_TEACHER_NAME,
        defaults={
            "weekly_capacity": 10**9,
            "limit_to_grades": False,
        }
    )
    return t


def _teacher_can_teach_class(teacher: Teacher, lesson: Lesson, school_class: SchoolClass) -> bool:
    # اگر مدل‌ها school دارند، باید هم‌مدرسه باشند
    if hasattr(teacher, "school_id") and hasattr(school_class, "school_id"):
        if teacher.school_id != school_class.school_id:
            return False

    # باید این درس توی lessons دبیر باشد
    if not teacher.lessons.filter(id=lesson.id).exists():
        return False

    # اگر محدود به پایه است، پایه کلاس باید توی grades دبیر باشد
    if teacher.limit_to_grades:
        return teacher.grades.filter(id=school_class.grade_id).exists()

    return True


def auto_assign_teachers(school=None, verbose=True):
    """
    ✅ هدف:
    - TeachingAssignmentItem کم نیاید (هیچ (کلاس،درس) اسکیپ نشود)
    - انتخاب هوشمند: اولویت با کارهایی که گزینه‌های دبیر کمتری دارند
    - allow_without_teacher=True -> بدون دبیر مجاز
    - اگر ظرفیت کم بود: باز هم آیتم ساخته شود ولی overload لاگ شود

    ✅ Multi-school:
    - اگر school پاس بدهی: فقط همان مدرسه پاک/ساخت می‌شود.
    """

    # اگر مدل‌ها school دارند، باید school مشخص باشد (یا تک مدرسه باشد)
    has_school = hasattr(TeachingAssignment, "school") or hasattr(Teacher, "school") or hasattr(SchoolClass, "school")

    if has_school and school is None:
        school = _pick_default_school_if_possible()
        if school is None:
            raise Exception("School مشخص نیست. auto_assign_teachers(school=...) را صدا بزنید.")

    logs = []

    def log(msg):
        logs.append(msg)
        if verbose:
            print(msg)

    with transaction.atomic():

        # -------------------------
        # 1) سابقه قبلی (برای ثبات)
        # -------------------------
        previous = {}
        prev_qs = TeachingAssignmentItem.objects.select_related("assignment__teacher")
        if has_school and school is not None and hasattr(TeachingAssignmentItem, "school"):
            prev_qs = prev_qs.filter(school=school)

        for item in prev_qs.all():
            if item.assignment_id and item.assignment.teacher_id:
                previous[(item.school_class_id, item.lesson_id)] = item.assignment.teacher_id

        # -------------------------
        # 2) پاک کردن قبلی‌ها فقط همان مدرسه
        # -------------------------
        if has_school and school is not None and hasattr(TeachingAssignmentItem, "school"):
            TeachingAssignmentItem.objects.filter(school=school).delete()
        else:
            TeachingAssignmentItem.objects.all().delete()

        if has_school and school is not None and hasattr(TeachingAssignment, "school"):
            TeachingAssignment.objects.filter(school=school).delete()
        else:
            TeachingAssignment.objects.all().delete()

        # -------------------------
        # 3) ظرفیت باقی‌مانده دبیرها (فقط همان مدرسه)
        # -------------------------
        t_qs = Teacher.objects.all()
        if has_school and school is not None and hasattr(Teacher, "school"):
            t_qs = t_qs.filter(school=school)

        teachers = list(t_qs)
        teacher_remaining = {t.id: int(t.weekly_capacity or 0) for t in teachers}

        # cache برای assignment هر teacher
        assignment_cache = {}

        def get_assignment_for(teacher: Teacher):
            if teacher.id in assignment_cache:
                return assignment_cache[teacher.id]

            if has_school and school is not None and hasattr(TeachingAssignment, "school"):
                a, _ = TeachingAssignment.objects.get_or_create(school=school, teacher=teacher)
            else:
                a, _ = TeachingAssignment.objects.get_or_create(teacher=teacher)

            assignment_cache[teacher.id] = a
            return a

        # -------------------------
        # 4) ساخت لیست همه نیازها (کلاس×درس) فقط همان مدرسه
        # -------------------------
        tasks = []  # (class, lesson, hours)

        c_qs = SchoolClass.objects.select_related("grade")
        if has_school and school is not None and hasattr(SchoolClass, "school"):
            c_qs = c_qs.filter(school=school)
        classes = list(c_qs)

        for c in classes:
            l_qs = Lesson.objects.filter(Q(for_all_grades=True) | Q(grades=c.grade)).distinct()
            if has_school and school is not None and hasattr(Lesson, "school"):
                l_qs = l_qs.filter(school=school)

            for l in l_qs:
                hours = int(l.weekly_hours or 0)
                if hours > 0:
                    tasks.append((c, l, hours))

        if not tasks:
            log("⚠ هیچ کاری برای AutoAssign پیدا نشد.")
            return logs

        # -------------------------
        # 5) کاندیدها
        # -------------------------
        task_candidates = {}
        for c, l, hours in tasks:
            cands = [t for t in teachers if _teacher_can_teach_class(t, l, c)]
            task_candidates[(c.id, l.id)] = cands

        # -------------------------
        # 6) مرتب‌سازی کارها
        # -------------------------
        def task_key(tup):
            c, l, hours = tup
            cands = task_candidates.get((c.id, l.id), [])
            cand_count = len(cands)

            prev_tid = previous.get((c.id, l.id))
            has_prev = 1 if prev_tid else 0

            return (cand_count, -hours, -has_prev)

        tasks.sort(key=task_key)

        expected = len(tasks)
        created = 0
        overload_count = 0

        # -------------------------
        # 7) انتخاب دبیر برای هر task
        # -------------------------
        for c, l, hours in tasks:
            cands = task_candidates.get((c.id, l.id), [])

            # اگر هیچ دبیر واجدی نبود:
            if not cands:
                if l.allow_without_teacher:
                    nt = get_no_teacher(school=school if has_school else None)
                    a = get_assignment_for(nt)

                    if has_school and school is not None and hasattr(TeachingAssignmentItem, "school"):
                        TeachingAssignmentItem.objects.create(
                            school=school,
                            assignment=a,
                            school_class=c,
                            lesson=l,
                            weekly_hours=hours
                        )
                    else:
                        TeachingAssignmentItem.objects.create(
                            assignment=a,
                            school_class=c,
                            lesson=l,
                            weekly_hours=hours
                        )

                    created += 1
                    log(f"✅ (بدون دبیر مجاز) {l.name} ({hours}h) -> کلاس {c.name}")
                    continue

                raise Exception(
                    f"هیچ دبیر واجدی برای درس «{l.name}» در کلاس «{c.name}» وجود ندارد. "
                    f"یا دبیر اضافه کن/درس را به دبیرها وصل کن، یا allow_without_teacher را فعال کن."
                )

            prev_tid = previous.get((c.id, l.id))

            def score(t: Teacher):
                prev_bonus = 10_000 if (prev_tid == t.id) else 0
                rem = teacher_remaining.get(t.id, 0)
                flex_penalty = 0
                if t.limit_to_grades:
                    flex_penalty = 50 * max(1, t.grades.count())
                return prev_bonus + rem - flex_penalty

            ok = [t for t in cands if teacher_remaining.get(t.id, 0) >= hours]
            if ok:
                ok.sort(key=score, reverse=True)
                chosen = ok[0]
            else:
                cands.sort(key=score, reverse=True)
                chosen = cands[0]
                overload_count += 1
                log(
                    f"⚠ overload: {chosen.name} برای {l.name}/{c.name} "
                    f"(نیاز={hours}, باقی={teacher_remaining.get(chosen.id,0)})"
                )

            a = get_assignment_for(chosen)

            if has_school and school is not None and hasattr(TeachingAssignmentItem, "school"):
                TeachingAssignmentItem.objects.create(
                    school=school,
                    assignment=a,
                    school_class=c,
                    lesson=l,
                    weekly_hours=hours
                )
            else:
                TeachingAssignmentItem.objects.create(
                    assignment=a,
                    school_class=c,
                    lesson=l,
                    weekly_hours=hours
                )

            created += 1
            teacher_remaining[chosen.id] = teacher_remaining.get(chosen.id, 0) - hours

        # -------------------------
        # 8) گزارش نهایی
        # -------------------------
        log(f"✅ AutoAssign تمام شد | ساخته شد: {created} | expected: {expected}")
        if created != expected:
            log("❌ هشدار: تعداد آیتم‌ها کمتر از expected شد (نباید اتفاق بیفتد).")

        if overload_count:
            log(f"⚠ تعداد overload ها: {overload_count}")

    return logs