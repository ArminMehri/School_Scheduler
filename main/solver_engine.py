from ortools.sat.python import cp_model
from django.db import transaction
from collections import defaultdict
from main.models import (
    TeachingAssignmentItem,
    Schedule,
    DayPeriod,
    TeacherAvailability,
)


def generate_schedule_with_ortools(max_time_seconds=60):
    """
    خروجی: list[str] لاگ‌ها

    قوانین:
    - هر اسلات 1 ساعته
    - هر کلاس در هر اسلات دقیقاً 1 درس (هیچ --- نداشته باشیم)
    - weekly_hours هر TeachingAssignmentItem دقیقاً رعایت شود
    - زوج‌ها: فقط به صورت بلوک‌های 2تایی پشت‌سرهم
    - فردها: بلوک‌های 2تایی پشت‌سرهم + دقیقاً 1 تک زنگ
    - 2+2 در یک روز ممنوع
    - 2+1 در یک روز سافت (جریمه دارد)
    - TeacherAvailability رعایت می‌شود:
        * اگر درس allow_without_teacher=False باشد: حضور دبیر اجباری است و فقط در روزهای مجازش می‌افتد
        * اگر allow_without_teacher=True باشد: درس می‌تواند بیاید ولی دبیر ممکن است None شود
    - سافت: تا حد امکان دبیر وسط روز بیکار (گپ) نماند
    """

    logs = []
    model = cp_model.CpModel()

    # ----------------------------
    # Slots
    # ----------------------------
    slots = list(
        DayPeriod.objects.filter(day__is_active=True)
        .select_related("day")
        .order_by("day__id", "period_number")
    )
    if not slots:
        raise Exception("هیچ زنگ فعالی تعریف نشده است.")

    slot_by_id = {s.id: s for s in slots}

    days = sorted(list({s.day for s in slots}), key=lambda d: d.id)
    day_slots = {
        d: sorted([s for s in slots if s.day == d], key=lambda s: s.period_number)
        for d in days
    }

    # همسایه‌ی بعدی (برای بلوک 2تایی)
    next_slot = {}
    prev_slot = {}
    for d in days:
        ordered = day_slots[d]
        for i in range(len(ordered) - 1):
            a, b = ordered[i], ordered[i + 1]
            if b.period_number == a.period_number + 1:
                next_slot[a.id] = b.id
                prev_slot[b.id] = a.id

    # ----------------------------
    # Items (TeachingAssignmentItem)
    # ----------------------------
    items = list(
        TeachingAssignmentItem.objects.select_related(
            "lesson", "school_class", "assignment__teacher"
        )
    )
    if not items:
        logs.append("⚠ هیچ TeachingAssignmentItem وجود ندارد.")
        return logs

    classes = sorted(list({i.school_class for i in items}), key=lambda c: c.id)

    # ----------------------------
    # TeacherAvailability dict
    # teacher_avail[teacher_id][day_id] = available_hours
    # ----------------------------
    teacher_avail = defaultdict(dict)
    for av in TeacherAvailability.objects.select_related("teacher", "day"):
        teacher_avail[av.teacher_id][av.day_id] = av.available_hours

    # ----------------------------
    # Decision vars
    # x[item, slot] = 1 اگر این item در این slot قرار بگیرد
    # t[item, slot] = 1 اگر معلم واقعاً در آن slot اعمال شود (اگر نشد 0 و teacher=None ذخیره می‌کنیم)
    # ----------------------------
    x = {}
    t = {}

    for it in items:
        for sl in slots:
            x[(it.id, sl.id)] = model.NewBoolVar(f"x_{it.id}_{sl.id}")
            t[(it.id, sl.id)] = model.NewBoolVar(f"t_{it.id}_{sl.id}")
            model.Add(t[(it.id, sl.id)] <= x[(it.id, sl.id)])  # اگر درس نیفتاد، دبیر هم نمی‌افتد

    # ----------------------------
    # HARD 1: هر کلاس در هر اسلات دقیقاً 1 درس
    # ----------------------------
    for sl in slots:
        for cls in classes:
            cls_items = [it for it in items if it.school_class_id == cls.id]
            model.Add(sum(x[(it.id, sl.id)] for it in cls_items) == 1)

    # ----------------------------
    # HARD 2: هر item دقیقاً weekly_hours بار بیاید
    # ----------------------------
    for it in items:
        model.Add(sum(x[(it.id, sl.id)] for sl in slots) == it.weekly_hours)

    # ----------------------------
    # Teacher constraints (با t)
    # - تداخل معلم در یک اسلات: sum(t) <= 1
    # - ظرفیت روزانه: sum(t in day) <= available_hours
    # - اگر درس "اجباری با دبیر" باشد -> t == x
    # - اگر دبیر در آن روز 0 ساعت دارد و درس اجباری است -> x آن روزها ممنوع
    # ----------------------------
    teachers = sorted(
        list({it.assignment.teacher for it in items if it.assignment and it.assignment.teacher}),
        key=lambda tt: tt.id
    )

    # تداخل
    for teacher in teachers:
        teacher_items = [it for it in items if it.assignment.teacher_id == teacher.id]
        for sl in slots:
            model.Add(sum(t[(it.id, sl.id)] for it in teacher_items) <= 1)

    # ظرفیت روزانه + لینک اجباری/اختیاری
    for it in items:
        teacher = it.assignment.teacher if it.assignment else None
        if not teacher:
            continue

        must_have_teacher = (not it.lesson.allow_without_teacher)

        for d in days:
            cap = teacher_avail.get(teacher.id, {}).get(d.id, 0)
            d_slots = day_slots[d]

            # ظرفیت روزانه با t کنترل می‌شود
            # (برای هر teacher روزانه یک بار محدود می‌کنیم، نه داخل حلقه item)
            # اما لینک اجباری/اختیاری را اینجا می‌زنیم:
            for sl in d_slots:
                if must_have_teacher:
                    # دبیر اجباری => t == x
                    model.Add(t[(it.id, sl.id)] == x[(it.id, sl.id)])

                    # اگر آن روز دبیر اصلاً حضور ندارد => x ممنوع
                    if cap <= 0:
                        model.Add(x[(it.id, sl.id)] == 0)

    # ظرفیت روزانه (جمع روی همه آیتم‌های آن معلم)
    for teacher in teachers:
        teacher_items = [it for it in items if it.assignment.teacher_id == teacher.id]
        for d in days:
            cap = teacher_avail.get(teacher.id, {}).get(d.id, 0)
            d_slots = day_slots[d]
            model.Add(
                sum(t[(it.id, sl.id)] for it in teacher_items for sl in d_slots) <= cap
            )

    # ----------------------------
    # BLOCK RULES
    # - زوج‌ها: فقط 2تایی (هیچ تک زنگی)
    # - فردها: دقیقاً یک تک زنگ + بقیه 2تایی
    # - 2+2 در روز ممنوع
    # - 2+1 در روز سافت
    # ----------------------------
    score_terms = []

    for it in items:
        total = it.weekly_hours
        doubles = total // 2
        singles = total % 2  # 0 یا 1

        # start2[it,slot] : شروع بلوک 2تایی از این slot (فقط اگر next_slot دارد)
        start2 = {}
        for sl in slots:
            if sl.id in next_slot:
                start2[(it.id, sl.id)] = model.NewBoolVar(f"start2_{it.id}_{sl.id}")

        # دقیقاً doubles تا بلوک 2تایی
        model.Add(sum(start2.values()) == doubles)

        # اگر start2 روشن شد => آن دو اسلات باید x=1 شوند
        for (iid, sid), st in start2.items():
            sid2 = next_slot[sid]
            model.Add(x[(it.id, sid)] == 1).OnlyEnforceIf(st)
            model.Add(x[(it.id, sid2)] == 1).OnlyEnforceIf(st)

        # پوشش زوج‌ها/فردها:
        # covered[slot] = start2 at slot OR start2 at prev(slot)
        # زوج: x <= covered
        # فرد: دقیقاً 1 slot "single_slot" که x=1 و covered=0
        covered = {}
        for sl in slots:
            cov_terms = []
            if (it.id, sl.id) in start2:
                cov_terms.append(start2[(it.id, sl.id)])
            prev_id = prev_slot.get(sl.id)
            if prev_id and (it.id, prev_id) in start2:
                cov_terms.append(start2[(it.id, prev_id)])

            cov = model.NewBoolVar(f"cov_{it.id}_{sl.id}")
            if cov_terms:
                model.Add(sum(cov_terms) >= 1).OnlyEnforceIf(cov)
                model.Add(sum(cov_terms) == 0).OnlyEnforceIf(cov.Not())
            else:
                model.Add(cov == 0)
            covered[sl.id] = cov

        if singles == 0:
            # هیچ تک زنگی نداریم => هر x باید تحت پوشش 2تایی باشد
            for sl in slots:
                model.Add(x[(it.id, sl.id)] <= covered[sl.id])
        else:
            # دقیقاً 1 تک زنگ: single_flag[slot] نشان می‌دهد این slot تک‌زنگ است
            single_flag = {}
            for sl in slots:
                sf = model.NewBoolVar(f"single_{it.id}_{sl.id}")
                single_flag[sl.id] = sf

                # تک‌زنگ فقط اگر آن slot واقعاً درس داشته باشد
                model.Add(sf <= x[(it.id, sl.id)])
                # تک‌زنگ یعنی این slot پوشش 2تایی نباشد
                model.Add(sf <= covered[sl.id].Not())

                # اگر slot پوشش نداشت و x=1 بود، باید یا single باشد یا خلاف قانون.
                # پس: x <= covered + single_flag
                model.Add(x[(it.id, sl.id)] <= covered[sl.id] + sf)

            model.Add(sum(single_flag.values()) == 1)

            # سافت: تک‌زنگ بهتره آخر روز باشد
            for d in days:
                ordered = day_slots[d]
                if not ordered:
                    continue
                last = ordered[-1]
                score_terms.append(2 * single_flag[last.id])

            # سافت: تک‌زنگ بهتره کنار paired باشد
            paired_lessons = list(it.lesson.paired_lessons.all())
            if paired_lessons:
                paired_items = [
                    j for j in items
                    if j.school_class_id == it.school_class_id and j.lesson in paired_lessons
                ]
                if paired_items:
                    for d in days:
                        ordered = day_slots[d]
                        for idx, sl in enumerate(ordered):
                            neighbors = []
                            if idx > 0:
                                neighbors.append(ordered[idx - 1])
                            if idx < len(ordered) - 1:
                                neighbors.append(ordered[idx + 1])
                            if not neighbors:
                                continue

                            # آیا یکی از paired ها در همسایه هست؟
                            neigh_has = model.NewBoolVar(f"paired_neigh_{it.id}_{sl.id}")
                            neigh_sum = []
                            for nb in neighbors:
                                neigh_sum.append(sum(x[(j.id, nb.id)] for j in paired_items))

                            model.Add(sum(neigh_sum) >= 1).OnlyEnforceIf(neigh_has)
                            model.Add(sum(neigh_sum) == 0).OnlyEnforceIf(neigh_has.Not())

                            together = model.NewBoolVar(f"single_with_pair_{it.id}_{sl.id}")
                            model.AddBoolAnd([single_flag[sl.id], neigh_has]).OnlyEnforceIf(together)
                            model.AddBoolOr([single_flag[sl.id].Not(), neigh_has.Not()]).OnlyEnforceIf(together.Not())

                            score_terms.append(3 * together)

        # HARD: 2+2 در یک روز ممنوع => start2 در هر روز <= 1
        for d in days:
            d_starts = []
            for sl in day_slots[d]:
                key = (it.id, sl.id)
                if key in start2:
                    d_starts.append(start2[key])
            if d_starts:
                model.Add(sum(d_starts) <= 1)

        # SOFT: 2+1 در یک روز جریمه
        if doubles >= 1 and singles == 1:
            for d in days:
                # has_double
                has_double = model.NewBoolVar(f"has_double_{it.id}_{d.id}")
                d_starts = []
                for sl in day_slots[d]:
                    key = (it.id, sl.id)
                    if key in start2:
                        d_starts.append(start2[key])
                if d_starts:
                    model.Add(sum(d_starts) >= 1).OnlyEnforceIf(has_double)
                    model.Add(sum(d_starts) == 0).OnlyEnforceIf(has_double.Not())
                else:
                    model.Add(has_double == 0)

                # has_three_slots_in_day یعنی 2+1 در همان روز (جمع x در روز == 3)
                has_three = model.NewBoolVar(f"has_three_{it.id}_{d.id}")
                model.Add(sum(x[(it.id, sl.id)] for sl in day_slots[d]) == 3).OnlyEnforceIf(has_three)
                model.Add(sum(x[(it.id, sl.id)] for sl in day_slots[d]) != 3).OnlyEnforceIf(has_three.Not())

                both = model.NewBoolVar(f"both_2p1_{it.id}_{d.id}")
                model.AddBoolAnd([has_double, has_three]).OnlyEnforceIf(both)
                model.AddBoolOr([has_double.Not(), has_three.Not()]).OnlyEnforceIf(both.Not())

                score_terms.append(-8 * both)

    # ----------------------------
    # SOFT: ترجیح زنگ‌های اول روز (1-3)
    # ----------------------------
    for it in items:
        for sl in slots:
            if sl.period_number <= 3:
                score_terms.append(1 * x[(it.id, sl.id)])

    # ----------------------------
    # SOFT: تا حد امکان "دبیر وسط روز بیکار نمونه"
    # ایده:
    # - برای هر معلم، اگر دو زنگ پشت‌سرهم تدریس داشته باشد => امتیاز +
    # - اگر یک زنگ تک افتاده باشد (قبل و بعدش خالی) => امتیاز -
    # - اگر الگوی گپ 1 تایی (کار-خالی-کار) باشد => امتیاز -
    # ----------------------------
    # ساخت work[teacher, slot] = sum(t items for that teacher in that slot) (۰/۱)
    work = {}
    for teacher in teachers:
        teacher_items = [it for it in items if it.assignment.teacher_id == teacher.id]
        for sl in slots:
            w = model.NewBoolVar(f"work_{teacher.id}_{sl.id}")
            model.Add(sum(t[(it.id, sl.id)] for it in teacher_items) == 1).OnlyEnforceIf(w)
            model.Add(sum(t[(it.id, sl.id)] for it in teacher_items) == 0).OnlyEnforceIf(w.Not())
            work[(teacher.id, sl.id)] = w

    # adjacency reward + isolated/gap penalty
    for teacher in teachers:
        for d in days:
            ordered = day_slots[d]
            for i, sl in enumerate(ordered):
                w = work[(teacher.id, sl.id)]

                prev_w = work[(teacher.id, ordered[i - 1].id)] if i > 0 else None
                next_w = work[(teacher.id, ordered[i + 1].id)] if i < len(ordered) - 1 else None

                # reward consecutive (w & next_w)
                if next_w is not None:
                    both = model.NewBoolVar(f"adj_{teacher.id}_{sl.id}")
                    model.AddBoolAnd([w, next_w]).OnlyEnforceIf(both)
                    model.AddBoolOr([w.Not(), next_w.Not()]).OnlyEnforceIf(both.Not())
                    score_terms.append(10 * both)  # امتیاز برای چسبیده بودن

                # penalty isolated: w=1 و prev=0 و next=0
                if prev_w is not None and next_w is not None:
                    iso = model.NewBoolVar(f"iso_{teacher.id}_{sl.id}")
                    model.AddBoolAnd([w, prev_w.Not(), next_w.Not()]).OnlyEnforceIf(iso)
                    model.AddBoolOr([w.Not(), prev_w, next_w]).OnlyEnforceIf(iso.Not())
                    score_terms.append(-18 * iso)

                # penalty gap pattern: work-0-work  (i, i+1, i+2)
                if i < len(ordered) - 2:
                    w1 = work[(teacher.id, ordered[i].id)]
                    w2 = work[(teacher.id, ordered[i + 1].id)]
                    w3 = work[(teacher.id, ordered[i + 2].id)]
                    gap = model.NewBoolVar(f"gap1_{teacher.id}_{ordered[i].id}")
                    model.AddBoolAnd([w1, w2.Not(), w3]).OnlyEnforceIf(gap)
                    model.AddBoolOr([w1.Not(), w2, w3.Not()]).OnlyEnforceIf(gap.Not())
                    score_terms.append(-14 * gap)

    # ----------------------------
    # SOFT: تا حد امکان دبیر واقعاً ست شود (برای درس‌هایی که اجازه می‌دهند)
    # ----------------------------
    for it in items:
        if it.lesson.allow_without_teacher:
            # اگر امکانش بود t را 1 کن (ولی اجباری نیست)
            for sl in slots:
                score_terms.append(6 * t[(it.id, sl.id)])

    # ----------------------------
    # هدف
    # ----------------------------
    model.Maximize(sum(score_terms) if score_terms else 0)

    # ----------------------------
    # Solve
    # ----------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max_time_seconds)

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise Exception("هیچ جدول معتبری پیدا نشد.")

    # ----------------------------
    # Save
    # ----------------------------
    with transaction.atomic():
        Schedule.objects.all().delete()

        for it in items:
            teacher = it.assignment.teacher if it.assignment else None

            for sl in slots:
                if solver.Value(x[(it.id, sl.id)]) == 1:
                    if teacher is None:
                        teacher_to_save = None
                    else:
                        teacher_used = (solver.Value(t[(it.id, sl.id)]) == 1)
                        teacher_to_save = teacher if teacher_used else None

                    Schedule.objects.create(
                        school_class=it.school_class,
                        day_period=sl,
                        lesson=it.lesson,
                        teacher=teacher_to_save
                    )

    logs.append("✅ برنامه با OR-Tools ساخته شد (با رعایت Availability و کاهش گپ دبیرها).")
    return logs
