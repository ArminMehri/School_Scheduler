from django.db import transaction
from django.db.models import Q

from main.models import (
    SchoolClass,
    Lesson,
    Teacher,
    TeachingAssignment,
    TeachingAssignmentItem,
)


NO_TEACHER_NAME = "بدون دبیر (سیستمی)"


def get_no_teacher():
    """
    فقط برای درس‌هایی که allow_without_teacher=True هست.
    چون مدل TeachingAssignmentItem حتماً assignment می‌خواهد و assignment هم teacher می‌خواهد،
    مجبوریم یک Teacher سیستمی داشته باشیم.
    """
    t, _ = Teacher.objects.get_or_create(
        name=NO_TEACHER_NAME,
        defaults={
            "weekly_capacity": 10**9,
            "limit_to_grades": False,
        }
    )
    return t


def _teacher_can_teach_class(teacher: Teacher, lesson: Lesson, school_class: SchoolClass) -> bool:
    # باید این درس توی lessons دبیر باشد
    if not teacher.lessons.filter(id=lesson.id).exists():
        return False

    # اگر محدود به پایه است، پایه کلاس باید توی grades دبیر باشد
    if teacher.limit_to_grades:
        return teacher.grades.filter(id=school_class.grade_id).exists()

    return True


def auto_assign_teachers(verbose=True):
    """
    ✅ هدف:
    - TeachingAssignmentItem کم نیاید (هیچ (کلاس،درس) اسکیپ نشود)
    - انتخاب هوشمند: اولویت با کارهایی که گزینه‌های دبیر کمتری دارند (تا نهم خالی نماند)
    - allow_without_teacher=True -> بدون دبیر مجاز
    - اگر ظرفیت کم بود: باز هم آیتم ساخته شود ولی overload لاگ شود
    """

    logs = []

    def log(msg):
        logs.append(msg)
        if verbose:
            print(msg)

    with transaction.atomic():

        # 1) سابقه قبلی (برای اولویت دادن به دبیر قبلی همان کلاس/درس)
        previous = {}
        for item in TeachingAssignmentItem.objects.select_related("assignment__teacher").all():
            if item.assignment_id and item.assignment.teacher_id:
                previous[(item.school_class_id, item.lesson_id)] = item.assignment.teacher_id

        # 2) پاک کردن قبلی‌ها (آیتم‌ها cascade می‌شن ولی این واضح‌تره)
        TeachingAssignmentItem.objects.all().delete()
        TeachingAssignment.objects.all().delete()

        # 3) ظرفیت باقی‌مانده
        teachers = list(Teacher.objects.all())
        teacher_remaining = {t.id: int(t.weekly_capacity or 0) for t in teachers}

        # cache برای assignment هر teacher
        assignment_cache = {}

        def get_assignment_for(teacher: Teacher):
            if teacher.id in assignment_cache:
                return assignment_cache[teacher.id]
            a, _ = TeachingAssignment.objects.get_or_create(teacher=teacher)
            assignment_cache[teacher.id] = a
            return a

        # 4) ساخت لیست “همه نیازها” (کلاس×درس)
        tasks = []  # (class, lesson, hours)
        classes = list(SchoolClass.objects.select_related("grade").all())

        for c in classes:
            lessons = (
                Lesson.objects.filter(
                    Q(for_all_grades=True) | Q(grades=c.grade)
                )
                .distinct()
            )
            for l in lessons:
                hours = int(l.weekly_hours or 0)
                if hours > 0:
                    tasks.append((c, l, hours))

        if not tasks:
            log("⚠ هیچ کاری برای AutoAssign پیدا نشد.")
            return logs

        # 5) برای هر task لیست کاندیدها را آماده کن
        # نکته: “کم گزینه‌ها” باید اول assign شوند تا پایه‌های حساس خالی نمانند.
        task_candidates = {}  # key=(class_id, lesson_id) -> [teachers]
        for c, l, hours in tasks:
            cands = [t for t in teachers if _teacher_can_teach_class(t, l, c)]
            task_candidates[(c.id, l.id)] = cands

        # 6) مرتب‌سازی کارها:
        # اول: تعداد کاندید کمتر (کارهای critical مثل نهم)
        # دوم: ساعات بیشتر
        # سوم: اگر دبیر قبلی داشت، آن را جلوتر می‌آوریم (ثبات)
        def task_key(tup):
            c, l, hours = tup
            cands = task_candidates.get((c.id, l.id), [])
            cand_count = len(cands)

            prev_tid = previous.get((c.id, l.id))
            has_prev = 1 if prev_tid else 0

            # cand_count کمتر => اول
            # hours بیشتر => اول
            # has_prev بیشتر => اول
            return (cand_count, -hours, -has_prev)

        tasks.sort(key=task_key)

        expected = len(tasks)
        created = 0
        overload_count = 0
        no_teacher_count = 0

        # 7) انتخاب دبیر برای هر task
        for c, l, hours in tasks:
            cands = task_candidates.get((c.id, l.id), [])

            # اگر هیچ دبیر واجدی نبود:
            if not cands:
                if l.allow_without_teacher:
                    # فقط برای allow_without_teacher
                    nt = get_no_teacher()
                    a = get_assignment_for(nt)
                    TeachingAssignmentItem.objects.create(
                        assignment=a,
                        school_class=c,
                        lesson=l,
                        weekly_hours=hours
                    )
                    created += 1
                    log(f"✅ (بدون دبیر مجاز) {l.name} ({hours}h) -> کلاس {c.name}")
                    continue
                else:
                    # اینجا واقعاً داده مشکل دارد: باید یک دبیر برای این درس تعریف کنی یا allow_without_teacher بزنی
                    no_teacher_count += 1
                    # برای اینکه item کم نیاید و solver نخوابد، مجبوریم overload کنیم اما فقط از بین دبیرهای مدرسه که اصلاً درس رو ندارند؟
                    # این کار غلط آموزشی است. پس بهتر: خطا بدهیم و توقف کنیم تا دیتای شما درست شود.
                    raise Exception(
                        f"هیچ دبیر واجدی برای درس «{l.name}» در کلاس «{c.name}» وجود ندارد. "
                        f"یا دبیر اضافه کن/درس را به دبیرها وصل کن، یا allow_without_teacher را فعال کن."
                    )

            # امتیازدهی دبیرها
            prev_tid = previous.get((c.id, l.id))

            def score(t: Teacher):
                # 1) اولویت با دبیر قبلی
                prev_bonus = 10_000 if (prev_tid == t.id) else 0

                # 2) هر چی ظرفیت باقی‌مانده بیشتر، بهتر
                rem = teacher_remaining.get(t.id, 0)

                # 3) دبیرهای محدود به پایه “کم انعطاف‌تر” هستند => بهتر است برای جاهای حساس نگه داشته شوند،
                # ولی چون tasks “کم گزینه” اول می‌آیند، همین کافی است.
                # اینجا فقط یک وزن کوچک می‌دهیم:
                flex_penalty = 0
                if t.limit_to_grades:
                    flex_penalty = 50 * max(1, t.grades.count())  # هر چی پایه‌های بیشتر، انعطاف بیشتر

                return prev_bonus + rem - flex_penalty

            # اول تلاش: دبیرهایی که ظرفیت کافی دارند
            ok = [t for t in cands if teacher_remaining.get(t.id, 0) >= hours]
            if ok:
                ok.sort(key=score, reverse=True)
                chosen = ok[0]
            else:
                # ظرفیت کافی نیست: برای اینکه آیتم کم نشود، overload می‌کنیم
                cands.sort(key=score, reverse=True)
                chosen = cands[0]
                overload_count += 1
                log(
                    f"⚠ overload: {chosen.name} برای {l.name}/{c.name} "
                    f"(نیاز={hours}, باقی={teacher_remaining.get(chosen.id,0)})"
                )

            a = get_assignment_for(chosen)
            TeachingAssignmentItem.objects.create(
                assignment=a,
                school_class=c,
                lesson=l,
                weekly_hours=hours
            )
            created += 1
            teacher_remaining[chosen.id] = teacher_remaining.get(chosen.id, 0) - hours

        # 8) گزارش نهایی
        log(f"✅ AutoAssign تمام شد | ساخته شد: {created} | expected: {expected}")
        if created != expected:
            log("❌ هشدار: تعداد آیتم‌ها کمتر از expected شد (نباید اتفاق بیفتد).")

        if overload_count:
            log(f"⚠ تعداد overload ها: {overload_count}")

        # این برای اینکه ببینی چرا مثلاً محمد محمدی کمتر پر شده:
        # (ممکنه طبیعی باشه چون الگوریتم کارهای کم‌گزینه را اول پر می‌کند)
        # ولی اگر بخوای “پر شدن حداکثری ظرفیت” هم داشته باشی، باید یک مرحله balancing اضافه کنیم.
        if verbose:
            for t in Teacher.objects.all():
                used = int(t.weekly_capacity or 0) - teacher_remaining.get(t.id, 0)
                if used < 0:
                    used = 0
                # فقط چندتا نمونه چاپ کن یا هرچی دوست داری
                # print(f"- {t.name}: used {used} / cap {t.weekly_capacity}")

    return logs
