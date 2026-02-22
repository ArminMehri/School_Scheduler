from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from main.services.auto_assign import auto_assign_teachers
from main.models import School
from main.models import (
    Grade, SchoolDay, DayPeriod,
    SchoolClass, Lesson, Teacher, TeacherAvailability,
    TeachingAssignment, TeachingAssignmentItem, Schedule
)

from .panel_forms import (
    GradeForm, SchoolDayForm, DayPeriodForm,
    SchoolClassForm, LessonForm, TeacherForm, TeacherAvailabilityForm,
    TeachingAssignmentForm, TeachingAssignmentItemForm,
    TeacherAvailabilityFormSet, TeachingItemInlineFormSet,
)

from .solver_engine import generate_schedule_with_ortools

try:
    from .views import export_schedule_excel, export_schedule_excel_teacher, export_schedule_pdf
except Exception:
    export_schedule_excel = None
    export_schedule_excel_teacher = None
    export_schedule_pdf = None


def _require_school(request):
    school = getattr(request.user, "school", None)
    if school is None:
        messages.error(request, "❌ این حساب به هیچ مدرسه‌ای وصل نیست.")
    return school

@require_POST
@login_required
def assignment_auto_assign(request):
    school = getattr(request.user, "school", None)
    if school is None:
        messages.error(request, "❌ این حساب به هیچ مدرسه‌ای وصل نیست.")
        return redirect("panel_dashboard")

    try:
        auto_assign_teachers(school=school, verbose=False)
        messages.success(request, "✅ AutoAssign انجام شد و TeachingAssignmentها ساخته شد.")
    except Exception as e:
        messages.error(request, f"❌ خطا در AutoAssign: {e}")

    return redirect("panel_dashboard")
@require_POST
@login_required
def panel_schedule_build(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    try:
        generate_schedule_with_ortools(school=school)
        messages.success(request, "✅ برنامه ساخته شد.")
    except Exception as e:
        messages.error(request, f"❌ خطا در ساخت برنامه: {e}")

    return redirect("schedule_list")

@require_POST
@login_required
def panel_schedule_clear(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    Schedule.objects.filter(school=school).delete()
    messages.success(request, "🗑️ برنامه‌های همین مدرسه پاک شد.")
    return redirect("schedule_list")
def _list_page(request, title, subtitle, add_url_name, headers, rows, actions=True, extra_buttons=None):
    return render(request, "panel/list.html", {
        "title": title,
        "subtitle": subtitle,
        "headers": headers,
        "rows": rows,
        "add_url_name": add_url_name,
        "actions": actions,
        "extra_buttons": extra_buttons or [],
    })


def _form_page(request, title, subtitle, form, cancel_url_name, formsets=None):
    return render(request, "panel/form.html", {
        "title": title,
        "subtitle": subtitle,
        "form": form,
        "cancel_url_name": cancel_url_name,
        "formsets": formsets or [],
    })


def _delete_page(request, title, subtitle, obj, cancel_url_name):
    return render(request, "panel/confirm_delete.html", {
        "title": title,
        "subtitle": subtitle,
        "object": obj,
        "cancel_url_name": cancel_url_name,
    })


def auth_login(request):
    if request.user.is_authenticated:
        return redirect("panel_dashboard")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = (request.POST.get("password") or "").strip()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "✅ وارد شدی.")
            return redirect("panel_dashboard")
        messages.error(request, "❌ نام کاربری یا رمز اشتباه است.")

    return render(request, "panel/auth_login.html")


def auth_register(request):
    if request.user.is_authenticated:
        return redirect("panel_dashboard")

    if request.method == "POST":
        User = get_user_model()

        username = (request.POST.get("username") or "").strip()
        password = (request.POST.get("password") or "").strip()
        password2 = (request.POST.get("password2") or "").strip()

        school_name = (request.POST.get("school_name") or "").strip()
        school_code = (request.POST.get("school_code") or "").strip()
        education_level = (request.POST.get("education_level") or "").strip()
        manager_mobile = (request.POST.get("manager_mobile") or "").strip()
        manager_full_name = (request.POST.get("manager_full_name") or "").strip()

        if not all([username, password, password2, school_name, school_code, education_level, manager_mobile, manager_full_name]):
            messages.error(request, "❌ لطفاً همه فیلدها را کامل کن.")
            return render(request, "panel/auth_register.html")

        if password != password2:
            messages.error(request, "❌ رمزها یکی نیستند.")
            return render(request, "panel/auth_register.html")

        if User.objects.filter(username=username).exists():
            messages.error(request, "❌ این نام کاربری قبلاً گرفته شده.")
            return render(request, "panel/auth_register.html")

        if School.objects.filter(code=school_code).exists():
            messages.error(request, "❌ این کد آموزشگاه قبلاً ثبت شده.")
            return render(request, "panel/auth_register.html")

        try:
            with transaction.atomic():
                school = School.objects.create(
                    name=school_name,
                    code=school_code,
                    education_level=education_level,
                    manager_full_name=manager_full_name,
                    manager_mobile=manager_mobile,
                )

                user = User.objects.create_user(
                    username=username,
                    password=password,
                )

                if hasattr(user, "school"):
                    user.school = school
                if hasattr(user, "phone"):
                    user.phone = manager_mobile
                if hasattr(user, "full_name"):
                    user.full_name = manager_full_name

                user.save()

            login(request, user)
            messages.success(request, "✅ ثبت نام انجام شد.")
            return redirect("panel_dashboard")

        except Exception as e:
            messages.error(request, f"❌ خطا در ثبت نام: {e}")
            return render(request, "panel/auth_register.html")

    return render(request, "panel/auth_register.html")


@login_required
def auth_logout(request):
    logout(request)
    messages.info(request, "👋 خارج شدی.")
    return redirect("panel_login")


@login_required
def panel_dashboard(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_logout")

    stats = [
        ("پایه‌ها", Grade.objects.filter(school=school).count(), "grade_list"),
        ("روزهای هفته", SchoolDay.objects.filter(school=school).count(), "schoolday_list"),
        ("زنگ‌ها", DayPeriod.objects.filter(school=school).count(), "dayperiod_list"),
        ("کلاس‌ها", SchoolClass.objects.filter(school=school).count(), "schoolclass_list"),
        ("درس‌ها", Lesson.objects.filter(school=school).count(), "lesson_list"),
        ("دبیرها", Teacher.objects.filter(school=school).count(), "teacher_list"),
        ("حضور دبیرها", TeacherAvailability.objects.filter(school=school).count(), "availability_list"),
        ("TeachingAssignments", TeachingAssignment.objects.filter(school=school).count(), "assignment_list"),
        ("TeachingItems", TeachingAssignmentItem.objects.filter(school=school).count(), "item_list"),
        ("برنامه‌ها", Schedule.objects.filter(school=school).count(), "schedule_list"),
    ]

    extra_buttons = [
        {"label": "⚙️ ساخت برنامه", "url_name": "generate_schedule", "method": "post", "style": "primary"},
        {"label": "🗑️ پاک کردن برنامه‌ها", "url_name": "schedule_clear", "method": "post", "style": "danger"},
    ]
    if export_schedule_excel:
        extra_buttons.append({"label": "📊 خروجی اکسل (کلاس‌محور)", "url_name": "export_excel_classes", "method": "get", "style": "ghost"})
    if export_schedule_excel_teacher:
        extra_buttons.append({"label": "📊 خروجی اکسل (دبیرمحور)", "url_name": "export_excel_teachers", "method": "get", "style": "ghost"})
    if export_schedule_pdf:
        extra_buttons.append({"label": "🧾 خروجی PDF", "url_name": "export_schedule_pdf", "method": "get", "style": "ghost"})

    return render(request, "panel/dashboard.html", {
        "title": "داشبورد",
        "subtitle": f"مدرسه: {school.name}",
        "stats": stats,
        "extra_buttons": extra_buttons,
    })


@require_POST
@login_required
def generate_schedule_view(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    try:
        generate_schedule_with_ortools(school=school)
        messages.success(request, "✅ برنامه ساخته شد.")
    except Exception as e:
        messages.error(request, f"❌ خطا در ساخت برنامه: {e}")
    return redirect("panel_dashboard")


@require_POST
@login_required
def schedule_clear(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    Schedule.objects.filter(school=school).delete()
    messages.success(request, "🗑️ برنامه‌های این مدرسه پاک شد.")
    return redirect("schedule_list")


@login_required
def export_excel_classes(request):
    if export_schedule_excel is None:
        messages.error(request, "❌ خروجی اکسل فعال نیست.")
        return redirect("panel_dashboard")
    return export_schedule_excel(request)


@login_required
def export_excel_teachers(request):
    if export_schedule_excel_teacher is None:
        messages.error(request, "❌ خروجی اکسل فعال نیست.")
        return redirect("panel_dashboard")
    return export_schedule_excel_teacher(request)


@login_required
def grade_list(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    qs = Grade.objects.filter(school=school).order_by("name")
    rows = [{
        "cols": [g.name],
        "edit_url": ("grade_update", g.id),
        "delete_url": ("grade_delete", g.id),
    } for g in qs]
    return _list_page(request, "پایه‌ها", "اضافه/ویرایش/حذف پایه‌ها", "grade_create", ["نام پایه"], rows)


@login_required
def grade_create(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    if request.method == "POST":
        form = GradeForm(request.POST, school=school)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            messages.success(request, "✅ پایه اضافه شد.")
            return redirect("grade_list")
    else:
        form = GradeForm(school=school)

    return _form_page(request, "افزودن پایه", "Grade جدید بساز", form, "grade_list")


@login_required
def grade_update(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    obj = get_object_or_404(Grade, pk=pk, school=school)
    if request.method == "POST":
        form = GradeForm(request.POST, instance=obj, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ پایه ویرایش شد.")
            return redirect("grade_list")
    else:
        form = GradeForm(instance=obj, school=school)

    return _form_page(request, "ویرایش پایه", f"ویرایش: {obj.name}", form, "grade_list")


@login_required
def grade_delete(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(Grade, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ پایه حذف شد.")
        return redirect("grade_list")
    return _delete_page(request, "حذف پایه", "مطمئنی حذفش کنیم؟", obj, "grade_list")


@login_required
def schoolday_list(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    qs = SchoolDay.objects.filter(school=school).order_by("id")
    rows = [{
        "cols": [d.name, "فعال ✅" if d.is_active else "تعطیل ⛔"],
        "edit_url": ("schoolday_update", d.id),
        "delete_url": ("schoolday_delete", d.id),
    } for d in qs]
    return _list_page(request, "روزهای هفته", "مدیریت روزهای هفته", "schoolday_create", ["روز", "وضعیت"], rows)


@login_required
def schoolday_create(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    if request.method == "POST":
        form = SchoolDayForm(request.POST, school=school)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            messages.success(request, "✅ روز اضافه شد.")
            return redirect("schoolday_list")
    else:
        form = SchoolDayForm(school=school)

    return _form_page(request, "افزودن روز", "روز جدید بساز", form, "schoolday_list")


@login_required
def schoolday_update(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(SchoolDay, pk=pk, school=school)

    if request.method == "POST":
        form = SchoolDayForm(request.POST, instance=obj, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ روز ویرایش شد.")
            return redirect("schoolday_list")
    else:
        form = SchoolDayForm(instance=obj, school=school)

    return _form_page(request, "ویرایش روز", f"ویرایش: {obj.name}", form, "schoolday_list")


@login_required
def schoolday_delete(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(SchoolDay, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ روز حذف شد.")
        return redirect("schoolday_list")
    return _delete_page(request, "حذف روز", "مطمئنی حذفش کنیم؟", obj, "schoolday_list")


@login_required
def dayperiod_list(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    qs = DayPeriod.objects.filter(school=school).select_related("day").order_by("day__id", "period_number")
    rows = [{
        "cols": [p.day.name, p.period_number],
        "edit_url": ("dayperiod_update", p.id),
        "delete_url": ("dayperiod_delete", p.id),
    } for p in qs]
    return _list_page(request, "زنگ‌ها", "مدیریت زنگ‌ها", "dayperiod_create", ["روز", "شماره زنگ"], rows)


@login_required
def dayperiod_create(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    if request.method == "POST":
        form = DayPeriodForm(request.POST, school=school)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            messages.success(request, "✅ زنگ اضافه شد.")
            return redirect("dayperiod_list")
    else:
        form = DayPeriodForm(school=school)

    return _form_page(request, "افزودن زنگ", "زنگ جدید بساز", form, "dayperiod_list")


@login_required
def dayperiod_update(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(DayPeriod, pk=pk, school=school)

    if request.method == "POST":
        form = DayPeriodForm(request.POST, instance=obj, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ زنگ ویرایش شد.")
            return redirect("dayperiod_list")
    else:
        form = DayPeriodForm(instance=obj, school=school)

    return _form_page(request, "ویرایش زنگ", f"ویرایش: {obj}", form, "dayperiod_list")


@login_required
def dayperiod_delete(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(DayPeriod, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ زنگ حذف شد.")
        return redirect("dayperiod_list")
    return _delete_page(request, "حذف زنگ", "مطمئنی حذفش کنیم؟", obj, "dayperiod_list")


@login_required
def schoolclass_list(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    qs = SchoolClass.objects.filter(school=school).select_related("grade").order_by("grade__name", "name")
    rows = [{
        "cols": [c.name, c.grade.name],
        "edit_url": ("schoolclass_update", c.id),
        "delete_url": ("schoolclass_delete", c.id),
    } for c in qs]
    return _list_page(request, "کلاس‌ها", "مدیریت کلاس‌ها", "schoolclass_create", ["کلاس", "پایه"], rows)


@login_required
def schoolclass_create(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    if request.method == "POST":
        form = SchoolClassForm(request.POST, school=school)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            messages.success(request, "✅ کلاس اضافه شد.")
            return redirect("schoolclass_list")
    else:
        form = SchoolClassForm(school=school)

    return _form_page(request, "افزودن کلاس", "کلاس جدید بساز", form, "schoolclass_list")


@login_required
def schoolclass_update(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(SchoolClass, pk=pk, school=school)

    if request.method == "POST":
        form = SchoolClassForm(request.POST, instance=obj, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ کلاس ویرایش شد.")
            return redirect("schoolclass_list")
    else:
        form = SchoolClassForm(instance=obj, school=school)

    return _form_page(request, "ویرایش کلاس", f"ویرایش: {obj.name}", form, "schoolclass_list")


@login_required
def schoolclass_delete(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(SchoolClass, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ کلاس حذف شد.")
        return redirect("schoolclass_list")
    return _delete_page(request, "حذف کلاس", "مطمئنی حذفش کنیم؟", obj, "schoolclass_list")


@login_required
def lesson_list(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    qs = Lesson.objects.filter(school=school).order_by("name")
    rows = [{
        "cols": [l.name, l.weekly_hours, "✅" if l.allow_without_teacher else "—"],
        "edit_url": ("lesson_update", l.id),
        "delete_url": ("lesson_delete", l.id),
    } for l in qs]
    return _list_page(request, "درس‌ها", "مدیریت درس‌ها", "lesson_create", ["نام درس", "ساعت/هفته", "بدون دبیر"], rows)


@login_required
def lesson_create(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    if request.method == "POST":
        form = LessonForm(request.POST, school=school)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            form.save_m2m()
            messages.success(request, "✅ درس اضافه شد.")
            return redirect("lesson_list")
    else:
        form = LessonForm(school=school)

    return _form_page(request, "افزودن درس", "درس جدید بساز", form, "lesson_list")


@login_required
def lesson_update(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(Lesson, pk=pk, school=school)

    if request.method == "POST":
        form = LessonForm(request.POST, instance=obj, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ درس ویرایش شد.")
            return redirect("lesson_list")
    else:
        form = LessonForm(instance=obj, school=school)

    return _form_page(request, "ویرایش درس", f"ویرایش: {obj.name}", form, "lesson_list")


@login_required
def lesson_delete(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(Lesson, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ درس حذف شد.")
        return redirect("lesson_list")
    return _delete_page(request, "حذف درس", "مطمئنی حذفش کنیم؟", obj, "lesson_list")


@login_required
def teacher_list(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    qs = Teacher.objects.filter(school=school).order_by("name")
    rows = [{
        "cols": [t.name, t.weekly_capacity],
        "edit_url": ("teacher_update", t.id),
        "delete_url": ("teacher_delete", t.id),
    } for t in qs]
    return _list_page(request, "دبیرها", "مدیریت دبیرها", "teacher_create", ["نام", "ظرفیت هفتگی"], rows)


@login_required
def teacher_create(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    if request.method == "POST":
        form = TeacherForm(request.POST, school=school)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            form.save_m2m()
            messages.success(request, "✅ دبیر اضافه شد.")
            return redirect("teacher_list")
    else:
        form = TeacherForm(school=school)

    return _form_page(request, "افزودن دبیر", "دبیر جدید بساز", form, "teacher_list")


@login_required
def teacher_update(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    teacher = get_object_or_404(Teacher, pk=pk, school=school)

    if request.method == "POST":
        form = TeacherForm(request.POST, instance=teacher, school=school)
        formset = TeacherAvailabilityFormSet(
            request.POST,
            instance=teacher,
            form_kwargs={"school": school}
        )

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()

                # save formset, ولی قبل از save شدن school رو ست کن
                avails = formset.save(commit=False)
                for a in avails:
                    a.school = school          # ✅ جلوگیری از خطای school_id
                    a.teacher = teacher        # ✅ اطمینان
                    a.save()

                # حذف‌های formset
                for obj in formset.deleted_objects:
                    obj.delete()

                formset.save_m2m()

            messages.success(request, "✅ دبیر و حضورهای دبیر ذخیره شد.")
            return redirect("teacher_list")

    else:
        form = TeacherForm(instance=teacher, school=school)
        formset = TeacherAvailabilityFormSet(
            instance=teacher,
            form_kwargs={"school": school}
        )

    return _form_page(
        request,
        "ویرایش دبیر",
        f"ویرایش: {teacher.name}",
        form,
        "teacher_list",
        formsets=[{"title": "حضور دبیر", "formset": formset}],
    )


@login_required
def teacher_delete(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(Teacher, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ دبیر حذف شد.")
        return redirect("teacher_list")
    return _delete_page(request, "حذف دبیر", "مطمئنی حذفش کنیم؟", obj, "teacher_list")


@login_required
def availability_list(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    qs = TeacherAvailability.objects.filter(school=school).select_related("teacher", "day").order_by("teacher__name", "day__id")
    rows = [{
        "cols": [a.teacher.name, a.day.name, a.available_hours],
        "edit_url": ("availability_update", a.id),
        "delete_url": ("availability_delete", a.id),
    } for a in qs]
    return _list_page(request, "حضور دبیرها", "مدیریت حضور دبیرها", "availability_create", ["دبیر", "روز", "ساعت"], rows)


@login_required
def availability_create(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    if request.method == "POST":
        form = TeacherAvailabilityForm(request.POST, school=school)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            messages.success(request, "✅ حضور اضافه شد.")
            return redirect("availability_list")
    else:
        form = TeacherAvailabilityForm(school=school)

    return _form_page(request, "افزودن حضور", "حضور جدید بساز", form, "availability_list")


@login_required
def availability_update(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(TeacherAvailability, pk=pk, school=school)

    if request.method == "POST":
        form = TeacherAvailabilityForm(request.POST, instance=obj, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ حضور ویرایش شد.")
            return redirect("availability_list")
    else:
        form = TeacherAvailabilityForm(instance=obj, school=school)

    return _form_page(request, "ویرایش حضور", f"ویرایش: {obj}", form, "availability_list")


@login_required
def availability_delete(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(TeacherAvailability, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ حضور حذف شد.")
        return redirect("availability_list")
    return _delete_page(request, "حذف حضور", "مطمئنی حذفش کنیم؟", obj, "availability_list")


@login_required
def assignment_list(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    qs = TeachingAssignment.objects.filter(school=school).select_related("teacher").order_by("teacher__name")
    rows = [{
        "cols": [a.teacher.name],
        "edit_url": ("assignment_update", a.id),
        "delete_url": ("assignment_delete", a.id),
    } for a in qs]
    return _list_page(request, "TeachingAssignments", "مدیریت تخصیص‌ها", "assignment_create", ["دبیر"], rows)


@login_required
def assignment_create(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    if request.method == "POST":
        form = TeachingAssignmentForm(request.POST, school=school)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            messages.success(request, "✅ تخصیص ساخته شد.")
            return redirect("assignment_list")
    else:
        form = TeachingAssignmentForm(school=school)
    return _form_page(request, "افزودن تخصیص", "تخصیص جدید بساز", form, "assignment_list")


@login_required
def assignment_update(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(TeachingAssignment, pk=pk, school=school)
    if request.method == "POST":
        form = TeachingAssignmentForm(request.POST, instance=obj, school=school)
    else:
        form = TeachingAssignmentForm(instance=obj, school=school)

    formset = TeachingItemInlineFormSet(request.POST or None, instance=obj, form_kwargs={"school": school})

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            items = formset.save(commit=False)
            for it in items:
                it.school = school
                if it.assignment_id is None:
                    it.assignment = obj
                it.save()
            for d in formset.deleted_objects:
                d.delete()
        messages.success(request, "✅ تخصیص و آیتم‌ها ذخیره شد.")
        return redirect("assignment_list")

    return _form_page(
        request,
        "ویرایش تخصیص",
        f"ویرایش: {obj.teacher.name}",
        form,
        "assignment_list",
        formsets=[{"title": "آیتم‌های تخصیص", "formset": formset}],
    )


@login_required
def assignment_delete(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(TeachingAssignment, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ تخصیص حذف شد.")
        return redirect("assignment_list")
    return _delete_page(request, "حذف تخصیص", "مطمئنی حذفش کنیم؟", obj, "assignment_list")


@login_required
def item_list(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    qs = TeachingAssignmentItem.objects.filter(school=school).select_related(
        "assignment__teacher", "school_class", "lesson"
    ).order_by("school_class__name", "lesson__name")
    rows = [{
        "cols": [i.assignment.teacher.name, i.school_class.name, i.lesson.name, i.weekly_hours],
        "edit_url": ("item_update", i.id),
        "delete_url": ("item_delete", i.id),
    } for i in qs]
    return _list_page(request, "TeachingItems", "مدیریت آیتم‌های تدریس", "item_create",
                      ["دبیر", "کلاس", "درس", "ساعت/هفته"], rows)


@login_required
def item_create(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    if request.method == "POST":
        form = TeachingAssignmentItemForm(request.POST, school=school)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.save()
            messages.success(request, "✅ آیتم اضافه شد.")
            return redirect("item_list")
    else:
        form = TeachingAssignmentItemForm(school=school)

    return _form_page(request, "افزودن آیتم", "آیتم جدید بساز", form, "item_list")


@login_required
def item_update(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(TeachingAssignmentItem, pk=pk, school=school)

    if request.method == "POST":
        form = TeachingAssignmentItemForm(request.POST, instance=obj, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ آیتم ویرایش شد.")
            return redirect("item_list")
    else:
        form = TeachingAssignmentItemForm(instance=obj, school=school)

    return _form_page(request, "ویرایش آیتم", f"ویرایش: {obj}", form, "item_list")


@login_required
def item_delete(request, pk):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")
    obj = get_object_or_404(TeachingAssignmentItem, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "🗑️ آیتم حذف شد.")
        return redirect("item_list")
    return _delete_page(request, "حذف آیتم", "مطمئنی حذفش کنیم؟", obj, "item_list")


@login_required
def schedule_list(request):
    school = _require_school(request)
    if school is None:
        return redirect("panel_dashboard")

    qs = Schedule.objects.filter(school=school).select_related(
        "school_class", "day_period__day", "lesson", "teacher"
    ).order_by("school_class__name", "day_period__day__id", "day_period__period_number")

    rows = []
    for s in qs:
        rows.append({
            "cols": [
                s.school_class.name,
                s.day_period.day.name,
                s.day_period.period_number,
                s.lesson.name,
                (s.teacher.name if s.teacher else "بدون دبیر"),
            ],
            "edit_url": None,
            "delete_url": None,
        })

    extra_buttons = [
        {"label": "⚙️ ساخت برنامه", "url_name": "generate_schedule", "method": "post", "style": "primary"},
        {"label": "🗑️ پاک کردن برنامه‌ها", "url_name": "schedule_clear", "method": "post", "style": "danger"},
    ]

    return _list_page(
        request,
        "برنامه‌ها",
        "لیست برنامه‌ی تولیدشده",
        add_url_name="",
        headers=["کلاس", "روز", "زنگ", "درس", "دبیر"],
        rows=rows,
        actions=False,
        extra_buttons=extra_buttons
    )