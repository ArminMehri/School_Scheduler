from ortools.sat.python import cp_model
from django.db import transaction
from collections import defaultdict
from main.models import (
    TeachingAssignmentItem,
    Schedule,
    DayPeriod,
    TeacherAvailability,
)
from main.services.progress import update_progress


def generate_schedule_with_ortools(max_time_seconds=180, school=None, strict_teacher_idle=True):
    """
    خروجی: list[str] لاگ‌ها
    قوانین:
    - هر اسلات 1 ساعته
    - هر کلاس در هر اسلات دقیقاً 1 درس
    - weekly_hours دقیقاً رعایت شود
    - زوج‌ها: فقط به صورت بلوک‌های 2تایی پشت‌سرهم
    - فردها: بلوک‌های 2تایی پشت‌سرهم + دقیقاً 1 تک زنگ
    - 2+2 در یک روز ممنوع
    - 2+1 در یک روز سافت (جریمه دارد)
    - TeacherAvailability رعایت می‌شود
    - تغییر جدید: تک زنگ وسط روز مجاز است اما امتیاز منفی دارد (-8)
    - تغییر جدید گپ‌ها:
        * گپ 1 تایی: ممنوع (Hard)
        * گپ 2 تایی: مجاز اما امتیاز منفی شدید (-500)
        * گپ 4 تایی و بیشتر: ممنوع (Hard)
    """
    if school is None:
        raise Exception("school مشخص نیست. generate_schedule_with_ortools(school=...) را صدا بزنید.")
    update_progress(school, 1, "شروع ساخت برنامه…")
    logs = []
    model = cp_model.CpModel()

    # ----------------------------
    # Slots
    # ----------------------------
    slots = list(
        DayPeriod.objects.filter(school=school, day__is_active=True)
        .select_related("day")
        .order_by("day__id", "period_number")
    )
    if not slots:
        raise Exception("هیچ زنگ فعالی تعریف نشده است.")
    update_progress(school, 10, f"زنگ‌ها آماده شد: {len(slots)} اسلات")
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
        TeachingAssignmentItem.objects.filter(school=school).select_related(
            "lesson", "school_class", "assignment__teacher"
        )
    )
    if not items:
        logs.append("⚠ هیچ TeachingAssignmentItem وجود ندارد.")
        return logs
    update_progress(school, 20, f"آیتم‌های تدریس آماده شد: {len(items)} مورد")
    classes = sorted(list({i.school_class for i in items}), key=lambda c: c.id)

    # ----------------------------
    # TeacherAvailability dict
    # ----------------------------
    teacher_avail = defaultdict(dict)
    for av in TeacherAvailability.objects.filter(school=school).select_related("teacher", "day"):
        teacher_avail[av.teacher_id][av.day_id] = av.available_hours

    # ----------------------------
    # Decision vars
    # ----------------------------
    x = {}
    t = {}
    for it in items:
        for sl in slots:
            x[(it.id, sl.id)] = model.NewBoolVar(f"x_{it.id}_{sl.id}")
            t[(it.id, sl.id)] = model.NewBoolVar(f"t_{it.id}_{sl.id}")
            model.Add(t[(it.id, sl.id)] <= x[(it.id, sl.id)])
    update_progress(school, 35, "متغیرهای تصمیم ساخته شد")

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
    update_progress(school, 45, "قیود سخت اعمال شد")

    # ----------------------------
    # Teacher constraints
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
            for sl in d_slots:
                if must_have_teacher:
                    model.Add(t[(it.id, sl.id)] == x[(it.id, sl.id)])
                    if cap <= 0:
                        model.Add(x[(it.id, sl.id)] == 0)
    # ظرفیت روزانه
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
    # ----------------------------
    score_terms = []
    for it in items:
        total = it.weekly_hours
        doubles = total // 2
        singles = total % 2

        start2 = {}
        for sl in slots:
            if sl.id in next_slot:
                start2[(it.id, sl.id)] = model.NewBoolVar(f"start2_{it.id}_{sl.id}")

        model.Add(sum(start2.values()) == doubles)

        for (iid, sid), st in start2.items():
            sid2 = next_slot[sid]
            model.Add(x[(it.id, sid)] == 1).OnlyEnforceIf(st)
            model.Add(x[(it.id, sid2)] == 1).OnlyEnforceIf(st)

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
            for sl in slots:
                model.Add(x[(it.id, sl.id)] <= covered[sl.id])
        else:
            single_flag = {}
            for sl in slots:
                sf = model.NewBoolVar(f"single_{it.id}_{sl.id}")
                single_flag[sl.id] = sf
                model.Add(sf <= x[(it.id, sl.id)])
                model.Add(sf <= covered[sl.id].Not())
                model.Add(x[(it.id, sl.id)] <= covered[sl.id] + sf)
            model.Add(sum(single_flag.values()) == 1)

            for d in days:
                ordered = day_slots[d]
                if len(ordered) >= 3:
                    for mid in ordered[1:-1]:
                        is_mid = model.NewBoolVar(f"is_mid_{it.id}_{mid.id}")
                        model.AddBoolAnd([single_flag[mid.id]]).OnlyEnforceIf(is_mid)
                        model.AddBoolOr([single_flag[mid.id].Not()]).OnlyEnforceIf(is_mid.Not())
                        score_terms.append(-8 * is_mid)

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
                            neigh_has = model.NewBoolVar(f"paired_neigh_{it.id}_{sl.id}")
                            neigh_sum = []
                            for nb in neighbors:
                                neigh_sum.append(sum(x[(j.id, nb.id)] for j in paired_items))
                            model.Add(sum(neigh_sum) >= 1).OnlyEnforceIf(neigh_has)
                            model.Add(sum(neigh_sum) == 0).OnlyEnforceIf(neigh_has.Not())
                            together = model.NewBoolVar(f"single_with_pair_{it.id}_{sl.id}")
                            model.AddBoolAnd([single_flag[sl.id], neigh_has]).OnlyEnforceIf(together)
                            model.AddBoolOr([single_flag[sl.id].Not(), neigh_has.Not()]).OnlyEnforceIf(together.Not())
                            model.Add(neigh_has == 1).OnlyEnforceIf(single_flag[sl.id])
                            score_terms.append(3 * together)

        for d in days:
            d_starts = []
            for sl in day_slots[d]:
                key = (it.id, sl.id)
                if key in start2:
                    d_starts.append(start2[key])
            if d_starts:
                model.Add(sum(d_starts) <= 1)

        if doubles >= 1 and singles == 1:
            for d in days:
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
                has_three = model.NewBoolVar(f"has_three_{it.id}_{d.id}")
                model.Add(sum(x[(it.id, sl.id)] for sl in day_slots[d]) == 3).OnlyEnforceIf(has_three)
                model.Add(sum(x[(it.id, sl.id)] for sl in day_slots[d]) != 3).OnlyEnforceIf(has_three.Not())
                both = model.NewBoolVar(f"both_2p1_{it.id}_{d.id}")
                model.AddBoolAnd([has_double, has_three]).OnlyEnforceIf(both)
                model.AddBoolOr([has_double.Not(), has_three.Not()]).OnlyEnforceIf(both.Not())
                score_terms.append(-8 * both)

    # ----------------------------
    # SOFT: Teacher Idle Logic
    # ----------------------------
    W_ADJ = 12
    W_ISO = 45
    W_GAP1 = 100  # فقط برای نمایش، چون Hard است استفاده نمیشود
    W_GAP2 = 500  # امتیاز منفی شدید برای گپ 2 تایی
    W_START = 18
    W_TRIPLE = 120

    work = {}
    for teacher in teachers:
        teacher_items = [it for it in items if it.assignment.teacher_id == teacher.id]
        for sl in slots:
            w = model.NewBoolVar(f"work_{teacher.id}_{sl.id}")
            model.Add(sum(t[(it.id, sl.id)] for it in teacher_items) == 1).OnlyEnforceIf(w)
            model.Add(sum(t[(it.id, sl.id)] for it in teacher_items) == 0).OnlyEnforceIf(w.Not())
            work[(teacher.id, sl.id)] = w

    for teacher in teachers:
        for d in days:
            ordered = day_slots[d]
            if not ordered:
                continue

            day_starts = []
            for i, sl in enumerate(ordered):
                w = work[(teacher.id, sl.id)]
                if i == 0:
                    st = model.NewBoolVar(f"start_{teacher.id}_{d.id}_{sl.id}")
                    model.Add(st == w)
                    day_starts.append(st)
                else:
                    prev_w = work[(teacher.id, ordered[i - 1].id)]
                    st = model.NewBoolVar(f"start_{teacher.id}_{d.id}_{sl.id}")
                    model.AddBoolAnd([w, prev_w.Not()]).OnlyEnforceIf(st)
                    model.AddBoolOr([w.Not(), prev_w]).OnlyEnforceIf(st.Not())
                    day_starts.append(st)
                    if strict_teacher_idle:
                        model.Add(sum(day_starts) <= 1)
            for st in day_starts:
                score_terms.append(-W_START * st)

            for i, sl in enumerate(ordered):
                w = work[(teacher.id, sl.id)]
                prev_w = work[(teacher.id, ordered[i - 1].id)] if i > 0 else None
                next_w = work[(teacher.id, ordered[i + 1].id)] if i < len(ordered) - 1 else None

                if next_w is not None:
                    both = model.NewBoolVar(f"adj_{teacher.id}_{sl.id}")
                    model.AddBoolAnd([w, next_w]).OnlyEnforceIf(both)
                    model.AddBoolOr([w.Not(), next_w.Not()]).OnlyEnforceIf(both.Not())
                    score_terms.append(W_ADJ * both)

                if prev_w is not None and next_w is not None:
                    iso = model.NewBoolVar(f"iso_{teacher.id}_{sl.id}")
                    model.AddBoolAnd([w, prev_w.Not(), next_w.Not()]).OnlyEnforceIf(iso)
                    model.AddBoolOr([w.Not(), prev_w, next_w]).OnlyEnforceIf(iso.Not())
                    score_terms.append(-W_ISO * iso)

                # --- گپ 1 تایی: ممنوع (Hard) ---
                if i < len(ordered) - 2:
                    w1 = work[(teacher.id, ordered[i].id)]
                    w2 = work[(teacher.id, ordered[i + 1].id)]
                    w3 = work[(teacher.id, ordered[i + 2].id)]
                    model.AddBoolOr([w1.Not(), w2, w3.Not()])

                # --- گپ 2 تایی: مجاز اما امتیاز منفی شدید (-500) ---
                if i < len(ordered) - 3:
                    w1 = work[(teacher.id, ordered[i].id)]
                    w2 = work[(teacher.id, ordered[i + 1].id)]
                    w3 = work[(teacher.id, ordered[i + 2].id)]
                    w4 = work[(teacher.id, ordered[i + 3].id)]
                    gap2 = model.NewBoolVar(f"gap2_{teacher.id}_{ordered[i].id}")
                    model.AddBoolAnd([w1, w2.Not(), w3.Not(), w4]).OnlyEnforceIf(gap2)
                    model.AddBoolOr([w1.Not(), w2, w3, w4.Not()]).OnlyEnforceIf(gap2.Not())
                    score_terms.append(-W_GAP2 * gap2)

                # --- گپ 3 تایی: جریمه شدید (مثل گپ 2) ---
                if i < len(ordered) - 4:
                    w1 = work[(teacher.id, ordered[i].id)]
                    w2 = work[(teacher.id, ordered[i + 1].id)]
                    w3 = work[(teacher.id, ordered[i + 2].id)]
                    w4 = work[(teacher.id, ordered[i + 3].id)]
                    w5 = work[(teacher.id, ordered[i + 4].id)]
                    gap3 = model.NewBoolVar(f"gap3_{teacher.id}_{ordered[i].id}")
                    model.AddBoolAnd([w1, w2.Not(), w3.Not(), w4.Not(), w5]).OnlyEnforceIf(gap3)
                    model.AddBoolOr([w1.Not(), w2, w3, w4, w5.Not()]).OnlyEnforceIf(gap3.Not())
                    score_terms.append(-W_GAP2 * gap3)

                # --- triple reward ---
                if i < len(ordered) - 2:
                    w1 = work[(teacher.id, ordered[i].id)]
                    w2 = work[(teacher.id, ordered[i + 1].id)]
                    w3 = work[(teacher.id, ordered[i + 2].id)]
                    triple = model.NewBoolVar(f"triple_{teacher.id}_{ordered[i].id}")
                    model.AddBoolAnd([w1, w2, w3]).OnlyEnforceIf(triple)
                    model.AddBoolOr([w1.Not(), w2.Not(), w3.Not()]).OnlyEnforceIf(triple.Not())
                    score_terms.append(-W_TRIPLE * triple)

            # --- گپ 4 تایی و بیشتر: ممنوع (Hard) ---
            # FIX: این حلقه باید بیرون از for i, sl باشد تا متغیر i بازنویسی نشود
            for ii in range(len(ordered)):
                for jj in range(ii + 4, len(ordered)):  # FIX: i+4 به جای i+5
                    middle = [work[(teacher.id, ordered[k].id)] for k in range(ii + 1, jj)]
                    if not middle:
                        continue
                    no_middle_work = model.NewBoolVar(
                        f"no_mid_work_{teacher.id}_{d.id}_{ii}_{jj}"
                    )
                    model.AddBoolAnd([m.Not() for m in middle]).OnlyEnforceIf(no_middle_work)
                    model.AddBoolOr(middle).OnlyEnforceIf(no_middle_work.Not())
                    model.AddBoolOr([
                        work[(teacher.id, ordered[ii].id)].Not(),
                        work[(teacher.id, ordered[jj].id)].Not(),
                        no_middle_work.Not(),
                    ])

    for it in items:
        if it.lesson.allow_without_teacher:
            for sl in slots:
                score_terms.append(6 * t[(it.id, sl.id)])

    model.Maximize(sum(score_terms) if score_terms else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max_time_seconds)
    update_progress(school, 55, "در حال حل مسئله (OR-Tools)…")
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if strict_teacher_idle:
            logs.append("⚠ حالت سختِ بدون پنجره دبیرها جواب نداد؛ تلاش مجدد با حالت نرم انجام شد.")
            return generate_schedule_with_ortools(
                max_time_seconds=max_time_seconds,
                school=school,
                strict_teacher_idle=False,
            )
        raise Exception("هیچ جدول معتبری پیدا نشد.")

    update_progress(school, 75, "حل انجام شد، در حال ذخیره برنامه…")

    with transaction.atomic():
        Schedule.objects.filter(school=school).delete()
        update_progress(school, 80, "برنامه قبلی پاک شد")
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
                        school=school,
                        school_class=it.school_class,
                        day_period=sl,
                        lesson=it.lesson,
                        teacher=teacher_to_save
                    )

    update_progress(school, 98, "ذخیره‌سازی تقریباً تمام شد…")
    logs.append("✅ برنامه با OR-Tools ساخته شد (گپ 1 ممنوع، گپ 2 جریمه شدید، گپ 4 ممنوع).")
    update_progress(school, 100, "✅ برنامه با موفقیت ساخته شد")
    return logs