from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from main.models import (
    Grade, SchoolDay, DayPeriod,
    SchoolClass, Lesson, Teacher, TeacherAvailability,
    TeachingAssignment, TeachingAssignmentItem, Schedule
)

from .panel_forms import (
    GradeForm, SchoolDayForm, DayPeriodForm,
    SchoolClassForm, LessonForm,
    TeacherForm, TeacherAvailabilityForm,
    TeachingAssignmentForm, TeachingAssignmentItemForm
)

from django.forms import inlineformset_factory

# ✅ Inline formset مثل admin
TeacherAvailabilityInlineFormSet = inlineformset_factory(
    Teacher,
    TeacherAvailability,
    form=TeacherAvailabilityForm,      # از panel_forms استفاده می‌کنیم
    fields=["day", "available_hours"], # teacher را از فرم حذف کردیم چون parent است
    extra=1,
    can_delete=True
)


# -------------------------
# Dashboard (همون استایل خفن)
# -------------------------
@login_required
def panel_dashboard(request):
    stats = [
        ("پایه‌ها", Grade.objects.count(), "panel/grades/"),
        ("روزهای هفته", SchoolDay.objects.count(), "panel/school-days/"),
        ("زنگ‌ها", DayPeriod.objects.count(), "panel/day-periods/"),
        ("کلاس‌ها", SchoolClass.objects.count(), "panel/classes/"),
        ("درس‌ها", Lesson.objects.count(), "panel/lessons/"),
        ("دبیرها", Teacher.objects.count(), "panel/teachers/"),
        ("حضور دبیرها", TeacherAvailability.objects.count(), "panel/availability/"),
        ("TeachingAssignments", TeachingAssignment.objects.count(), "panel/teaching-assignments/"),
        ("TeachingItems", TeachingAssignmentItem.objects.count(), "panel/teaching-items/"),
        ("برنامه‌ها", Schedule.objects.count(), "panel/schedule/"),
    ]
    return render(request, "panel/dashboard.html", {"stats": stats})


# -------------------------
# Generic helpers
# -------------------------
def _list_page(request, title, subtitle, add_url_name, headers, rows, actions=True):
    return render(request, "panel/list.html", {
        "title": title,
        "subtitle": subtitle,
        "headers": headers,
        "rows": rows,
        "add_url_name": add_url_name,
        "actions": actions,
    })

def _form_page(request, title, subtitle, form, cancel_url_name):
    return render(request, "panel/form.html", {
        "title": title,
        "subtitle": subtitle,
        "form": form,
        "cancel_url_name": cancel_url_name,
    })

def _delete_page(request, title, subtitle, obj, cancel_url_name):
    return render(request, "panel/confirm_delete.html", {
        "title": title,
        "subtitle": subtitle,
        "obj": obj,
        "cancel_url_name": cancel_url_name,
    })


# -------------------------
# Grades CRUD
# -------------------------
@login_required
def grade_list(request):
    qs = Grade.objects.all().order_by("name")
    rows = []
    for g in qs:
        rows.append({
            "cols": [g.name],
            "edit_url": ("grade_update", g.id),
            "delete_url": ("grade_delete", g.id),
        })
    return _list_page(request, "پایه‌ها", "اضافه/ویرایش/حذف پایه‌ها", "grade_create", ["نام پایه"], rows)

@login_required
def grade_create(request):
    if request.method == "POST":
        form = GradeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ پایه اضافه شد.")
            return redirect("grade_list")
    else:
        form = GradeForm()
    return _form_page(request, "افزودن پایه", "Grade جدید بساز", form, "grade_list")

@login_required
def grade_update(request, pk):
    obj = get_object_or_404(Grade, pk=pk)
    if request.method == "POST":
        form = GradeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ پایه ویرایش شد.")
            return redirect("grade_list")
    else:
        form = GradeForm(instance=obj)
    return _form_page(request, "ویرایش پایه", f"ویرایش: {obj.name}", form, "grade_list")

@login_required
def grade_delete(request, pk):
    obj = get_object_or_404(Grade, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ پایه حذف شد.")
        return redirect("grade_list")
    return _delete_page(request, "حذف پایه", "مطمئنی حذفش کنیم؟", obj, "grade_list")


# -------------------------
# SchoolDay CRUD
# -------------------------
@login_required
def schoolday_list(request):
    qs = SchoolDay.objects.all().order_by("id")
    rows = []
    for d in qs:
        rows.append({
            "cols": [d.name, "فعال ✅" if d.is_active else "تعطیل ⛔"],
            "edit_url": ("schoolday_update", d.id),
            "delete_url": ("schoolday_delete", d.id),
        })
    return _list_page(request, "روزهای هفته", "مدیریت روزهای هفته", "schoolday_create", ["روز", "وضعیت"], rows)

@login_required
def schoolday_create(request):
    if request.method == "POST":
        form = SchoolDayForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ روز اضافه شد.")
            return redirect("schoolday_list")
    else:
        form = SchoolDayForm()
    return _form_page(request, "افزودن روز", "SchoolDay جدید بساز", form, "schoolday_list")

@login_required
def schoolday_update(request, pk):
    obj = get_object_or_404(SchoolDay, pk=pk)
    if request.method == "POST":
        form = SchoolDayForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ روز ویرایش شد.")
            return redirect("schoolday_list")
    else:
        form = SchoolDayForm(instance=obj)
    return _form_page(request, "ویرایش روز", f"ویرایش: {obj.name}", form, "schoolday_list")

@login_required
def schoolday_delete(request, pk):
    obj = get_object_or_404(SchoolDay, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ روز حذف شد.")
        return redirect("schoolday_list")
    return _delete_page(request, "حذف روز", "مطمئنی حذفش کنیم؟", obj, "schoolday_list")


# -------------------------
# DayPeriod CRUD
# -------------------------
@login_required
def dayperiod_list(request):
    qs = DayPeriod.objects.select_related("day").all().order_by("day__id", "period_number")
    rows = []
    for p in qs:
        rows.append({
            "cols": [p.day.name, f"زنگ {p.period_number}"],
            "edit_url": ("dayperiod_update", p.id),
            "delete_url": ("dayperiod_delete", p.id),
        })
    return _list_page(request, "زنگ‌ها", "مدیریت DayPeriod ها", "dayperiod_create", ["روز", "زنگ"], rows)

@login_required
def dayperiod_create(request):
    if request.method == "POST":
        form = DayPeriodForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ زنگ اضافه شد.")
            return redirect("dayperiod_list")
    else:
        form = DayPeriodForm()
    return _form_page(request, "افزودن زنگ", "DayPeriod جدید بساز", form, "dayperiod_list")

@login_required
def dayperiod_update(request, pk):
    obj = get_object_or_404(DayPeriod, pk=pk)
    if request.method == "POST":
        form = DayPeriodForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ زنگ ویرایش شد.")
            return redirect("dayperiod_list")
    else:
        form = DayPeriodForm(instance=obj)
    return _form_page(request, "ویرایش زنگ", f"ویرایش: {obj}", form, "dayperiod_list")

@login_required
def dayperiod_delete(request, pk):
    obj = get_object_or_404(DayPeriod, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ زنگ حذف شد.")
        return redirect("dayperiod_list")
    return _delete_page(request, "حذف زنگ", "مطمئنی حذفش کنیم؟", obj, "dayperiod_list")


# -------------------------
# SchoolClass CRUD
# -------------------------
@login_required
def schoolclass_list(request):
    qs = SchoolClass.objects.select_related("grade").all().order_by("grade__name", "name")
    rows = []
    for c in qs:
        rows.append({
            "cols": [c.name, c.grade.name],
            "edit_url": ("schoolclass_update", c.id),
            "delete_url": ("schoolclass_delete", c.id),
        })
    return _list_page(request, "کلاس‌ها", "مدیریت کلاس‌ها", "schoolclass_create", ["نام کلاس", "پایه"], rows)

@login_required
def schoolclass_create(request):
    if request.method == "POST":
        form = SchoolClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ کلاس اضافه شد.")
            return redirect("schoolclass_list")
    else:
        form = SchoolClassForm()
    return _form_page(request, "افزودن کلاس", "SchoolClass جدید بساز", form, "schoolclass_list")

@login_required
def schoolclass_update(request, pk):
    obj = get_object_or_404(SchoolClass, pk=pk)
    if request.method == "POST":
        form = SchoolClassForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ کلاس ویرایش شد.")
            return redirect("schoolclass_list")
    else:
        form = SchoolClassForm(instance=obj)
    return _form_page(request, "ویرایش کلاس", f"ویرایش: {obj.name}", form, "schoolclass_list")

@login_required
def schoolclass_delete(request, pk):
    obj = get_object_or_404(SchoolClass, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ کلاس حذف شد.")
        return redirect("schoolclass_list")
    return _delete_page(request, "حذف کلاس", "مطمئنی حذفش کنیم؟", obj, "schoolclass_list")


# -------------------------
# Lesson CRUD
# -------------------------
@login_required
def lesson_list(request):
    qs = Lesson.objects.all().order_by("name")
    rows = []
    for l in qs:
        rows.append({
            "cols": [
                l.name,
                str(l.weekly_hours),
                "✅" if l.for_all_grades else "—",
                "✅" if l.allow_without_teacher else "⛔",
            ],
            "edit_url": ("lesson_update", l.id),
            "delete_url": ("lesson_delete", l.id),
        })
    return _list_page(request, "درس‌ها", "مدیریت درس‌ها", "lesson_create",
                      ["نام", "ساعت/هفته", "برای همه پایه‌ها", "بدون دبیر مجاز؟"], rows)

@login_required
def lesson_create(request):
    if request.method == "POST":
        form = LessonForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ درس اضافه شد.")
            return redirect("lesson_list")
    else:
        form = LessonForm()
    return _form_page(request, "افزودن درس", "Lesson جدید بساز", form, "lesson_list")

@login_required
def lesson_update(request, pk):
    obj = get_object_or_404(Lesson, pk=pk)
    if request.method == "POST":
        form = LessonForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ درس ویرایش شد.")
            return redirect("lesson_list")
    else:
        form = LessonForm(instance=obj)
    return _form_page(request, "ویرایش درس", f"ویرایش: {obj.name}", form, "lesson_list")

@login_required
def lesson_delete(request, pk):
    obj = get_object_or_404(Lesson, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ درس حذف شد.")
        return redirect("lesson_list")
    return _delete_page(request, "حذف درس", "مطمئنی حذفش کنیم؟", obj, "lesson_list")


# -------------------------
# Teacher CRUD (با inline حضور دبیر)
# -------------------------
@login_required
def teacher_list(request):
    qs = Teacher.objects.all().order_by("name")
    rows = []
    for t in qs:
        rows.append({
            "cols": [t.name, str(t.weekly_capacity), "✅" if t.limit_to_grades else "—"],
            "edit_url": ("teacher_update", t.id),
            "delete_url": ("teacher_delete", t.id),
        })
    return _list_page(request, "دبیرها", "مدیریت دبیرها + حضور دبیر داخل ویرایش", "teacher_create",
                      ["نام", "ظرفیت هفتگی", "محدود به پایه؟"], rows)


@login_required
def teacher_create(request):
    teacher = Teacher()
    if request.method == "POST":
        form = TeacherForm(request.POST, instance=teacher)
        formset = TeacherAvailabilityInlineFormSet(request.POST, instance=teacher)
        if form.is_valid() and formset.is_valid():
            teacher = form.save()
            formset.instance = teacher
            formset.save()
            messages.success(request, "✅ دبیر + حضور هفتگی ثبت شد.")
            return redirect("teacher_list")
    else:
        form = TeacherForm(instance=teacher)
        formset = TeacherAvailabilityInlineFormSet(instance=teacher)

    return render(request, "panel/teacher_form_inline.html", {
        "title": "افزودن دبیر",
        "subtitle": "ثبت دبیر + حضور در روزهای هفته",
        "form": form,
        "formset": formset,
        "cancel_url_name": "teacher_list",
        "is_edit": False,
    })


@login_required
def teacher_update(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)

    if request.method == "POST":
        form = TeacherForm(request.POST, instance=teacher)
        formset = TeacherAvailabilityInlineFormSet(request.POST, instance=teacher)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "✅ اطلاعات دبیر و حضور ذخیره شد.")
            return redirect("teacher_list")
    else:
        form = TeacherForm(instance=teacher)
        formset = TeacherAvailabilityInlineFormSet(instance=teacher)

    return render(request, "panel/teacher_form_inline.html", {
        "title": "ویرایش دبیر",
        "subtitle": f"ویرایش: {teacher.name}",
        "form": form,
        "formset": formset,
        "cancel_url_name": "teacher_list",
        "is_edit": True,
        "teacher": teacher
    })


@login_required
def teacher_delete(request, pk):
    obj = get_object_or_404(Teacher, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ دبیر حذف شد.")
        return redirect("teacher_list")
    return _delete_page(request, "حذف دبیر", "مطمئنی حذفش کنیم؟", obj, "teacher_list")

# -------------------------
# TeacherAvailability CRUD
# -------------------------
@login_required
def availability_list(request):
    qs = TeacherAvailability.objects.select_related("teacher", "day").all().order_by("teacher__name", "day__id")
    rows = []
    for a in qs:
        rows.append({
            "cols": [a.teacher.name, a.day.name, str(a.available_hours)],
            "edit_url": ("availability_update", a.id),
            "delete_url": ("availability_delete", a.id),
        })
    return _list_page(request, "حضور دبیرها", "مدیریت TeacherAvailability", "availability_create",
                      ["دبیر", "روز", "ساعت"], rows)

@login_required
def availability_create(request):
    if request.method == "POST":
        form = TeacherAvailabilityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ حضور دبیر ثبت شد.")
            return redirect("availability_list")
    else:
        form = TeacherAvailabilityForm()
    return _form_page(request, "افزودن حضور دبیر", "TeacherAvailability جدید", form, "availability_list")

@login_required
def availability_update(request, pk):
    obj = get_object_or_404(TeacherAvailability, pk=pk)
    if request.method == "POST":
        form = TeacherAvailabilityForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ حضور دبیر ویرایش شد.")
            return redirect("availability_list")
    else:
        form = TeacherAvailabilityForm(instance=obj)
    return _form_page(request, "ویرایش حضور دبیر", f"ویرایش: {obj}", form, "availability_list")

@login_required
def availability_delete(request, pk):
    obj = get_object_or_404(TeacherAvailability, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ حضور دبیر حذف شد.")
        return redirect("availability_list")
    return _delete_page(request, "حذف حضور دبیر", "مطمئنی حذفش کنیم؟", obj, "availability_list")


# -------------------------
# TeachingAssignment CRUD
# -------------------------
@login_required
def assignment_list(request):
    qs = TeachingAssignment.objects.select_related("teacher").all().order_by("teacher__name")
    rows = []
    for a in qs:
        rows.append({
            "cols": [a.teacher.name],
            "edit_url": ("assignment_update", a.id),
            "delete_url": ("assignment_delete", a.id),
        })
    return _list_page(request, "TeachingAssignments", "هر دبیر یک Assignment دارد", "assignment_create",
                      ["دبیر"], rows)

@login_required
def assignment_create(request):
    if request.method == "POST":
        form = TeachingAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Assignment ساخته شد.")
            return redirect("assignment_list")
    else:
        form = TeachingAssignmentForm()
    return _form_page(request, "افزودن Assignment", "TeachingAssignment جدید", form, "assignment_list")

@login_required
def assignment_update(request, pk):
    obj = get_object_or_404(TeachingAssignment, pk=pk)
    if request.method == "POST":
        form = TeachingAssignmentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Assignment ویرایش شد.")
            return redirect("assignment_list")
    else:
        form = TeachingAssignmentForm(instance=obj)
    return _form_page(request, "ویرایش Assignment", f"ویرایش: {obj.teacher.name}", form, "assignment_list")

@login_required
def assignment_delete(request, pk):
    obj = get_object_or_404(TeachingAssignment, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ Assignment حذف شد.")
        return redirect("assignment_list")
    return _delete_page(request, "حذف Assignment", "مطمئنی حذفش کنیم؟", obj, "assignment_list")


# -------------------------
# TeachingAssignmentItem CRUD
# -------------------------
@login_required
def item_list(request):
    qs = TeachingAssignmentItem.objects.select_related("assignment__teacher", "school_class", "lesson")\
        .all().order_by("school_class__name", "lesson__name")
    rows = []
    for it in qs:
        rows.append({
            "cols": [
                it.school_class.name,
                it.lesson.name,
                str(it.weekly_hours),
                it.assignment.teacher.name if it.assignment else "—",
            ],
            "edit_url": ("item_update", it.id),
            "delete_url": ("item_delete", it.id),
        })
    return _list_page(request, "TeachingAssignmentItems", "کلاس + درس + ساعت + دبیر", "item_create",
                      ["کلاس", "درس", "ساعت", "دبیر"], rows)

@login_required
def item_create(request):
    if request.method == "POST":
        form = TeachingAssignmentItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ آیتم تدریس اضافه شد.")
            return redirect("item_list")
    else:
        form = TeachingAssignmentItemForm()
    return _form_page(request, "افزودن آیتم تدریس", "TeachingAssignmentItem جدید", form, "item_list")

@login_required
def item_update(request, pk):
    obj = get_object_or_404(TeachingAssignmentItem, pk=pk)
    if request.method == "POST":
        form = TeachingAssignmentItemForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ آیتم تدریس ویرایش شد.")
            return redirect("item_list")
    else:
        form = TeachingAssignmentItemForm(instance=obj)
    return _form_page(request, "ویرایش آیتم تدریس", f"ویرایش: {obj}", form, "item_list")

@login_required
def item_delete(request, pk):
    obj = get_object_or_404(TeachingAssignmentItem, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ آیتم تدریس حذف شد.")
        return redirect("item_list")
    return _delete_page(request, "حذف آیتم تدریس", "مطمئنی حذفش کنیم؟", obj, "item_list")


# -------------------------
# Schedule (فقط نمایش)
# -------------------------
@login_required
def schedule_list(request):
    qs = Schedule.objects.select_related("school_class", "lesson", "teacher", "day_period", "day_period__day")\
        .all().order_by("school_class__name", "day_period__day__id", "day_period__period_number")

    rows = []
    for s in qs:
        rows.append({
            "cols": [
                s.school_class.name,
                s.day_period.day.name,
                str(s.day_period.period_number),
                s.lesson.name,
                s.teacher.name if s.teacher else "بدون دبیر",
            ],
            "edit_url": None,
            "delete_url": None,
        })

    return _list_page(
        request,
        "برنامه‌ها",
        "Schedule ساخته شده (نمایش)",
        add_url_name=None,
        headers=["کلاس", "روز", "زنگ", "درس", "دبیر"],
        rows=rows,
        actions=False
    )
