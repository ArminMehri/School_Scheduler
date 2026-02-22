from django import forms
from django.forms import inlineformset_factory

from main.models import (
    Grade, SchoolDay, DayPeriod,
    SchoolClass, Lesson, Teacher, TeacherAvailability,
    TeachingAssignment, TeachingAssignmentItem
)

# ✅ ورودی‌های دارک/گلس (دیگه سفید نمیشن)
BASE_INPUT = (
    "w-full rounded-2xl border border-white/10 "
    "bg-white/10 text-slate-100 placeholder-slate-400 "
    "px-4 py-3 "
    "focus:outline-none focus:ring-2 focus:ring-blue-400/60 "
    "focus:border-blue-400/50 "
)

BASE_SELECT = (
    "w-full rounded-2xl border border-white/10 "
    "bg-white/10 text-slate-100 "
    "px-4 py-3 "
    "focus:outline-none focus:ring-2 focus:ring-blue-400/60 "
    "focus:border-blue-400/50 "
)

BASE_TEXTAREA = (
    "w-full rounded-2xl border border-white/10 "
    "bg-white/10 text-slate-100 placeholder-slate-400 "
    "px-4 py-3 "
    "focus:outline-none focus:ring-2 focus:ring-blue-400/60 "
    "focus:border-blue-400/50 "
)

BASE_CHECK = "h-5 w-5 rounded border-white/20 bg-white/10 text-blue-500"


class SchoolScopedModelForm(forms.ModelForm):
    """Form base: اگر مدرسه دادیم، queryset فیلدهای FK/M2M مدرسه‌ای می‌شود."""

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school
        if school is not None:
            self._apply_school_scope(school)

    def _apply_school_scope(self, school):
        for _, field in self.fields.items():
            qs = getattr(field, "queryset", None)
            if qs is None:
                continue
            model = getattr(qs, "model", None)
            if model is None:
                continue
            try:
                if "school" in [f.name for f in model._meta.fields]:
                    field.queryset = qs.filter(school=school)
            except Exception:
                pass


class GradeForm(SchoolScopedModelForm):
    class Meta:
        model = Grade
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "مثلا هفتم"})
        }


class SchoolDayForm(SchoolScopedModelForm):
    class Meta:
        model = SchoolDay
        fields = ["name", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "مثلا شنبه"}),
            "is_active": forms.CheckboxInput(attrs={"class": BASE_CHECK}),
        }


class DayPeriodForm(SchoolScopedModelForm):
    class Meta:
        model = DayPeriod
        fields = ["day", "period_number"]
        widgets = {
            "day": forms.Select(attrs={"class": BASE_SELECT}),
            "period_number": forms.NumberInput(attrs={"class": BASE_INPUT, "min": 1}),
        }


class SchoolClassForm(SchoolScopedModelForm):
    class Meta:
        model = SchoolClass
        fields = ["name", "grade"]
        widgets = {
            "name": forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "مثلا 701"}),
            "grade": forms.Select(attrs={"class": BASE_SELECT}),
        }


class LessonForm(SchoolScopedModelForm):
    class Meta:
        model = Lesson
        fields = [
            "name", "weekly_hours", "for_all_grades", "grades",
            "allow_split", "paired_lessons", "allow_without_teacher"
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "مثلا ریاضی"}),
            "weekly_hours": forms.NumberInput(attrs={"class": BASE_INPUT, "min": 0}),
            "for_all_grades": forms.CheckboxInput(attrs={"class": BASE_CHECK}),
            "grades": forms.SelectMultiple(attrs={"class": BASE_SELECT, "size": 6}),
            "allow_split": forms.CheckboxInput(attrs={"class": BASE_CHECK}),
            "paired_lessons": forms.SelectMultiple(attrs={"class": BASE_SELECT, "size": 6}),
            "allow_without_teacher": forms.CheckboxInput(attrs={"class": BASE_CHECK}),
        }


class TeacherForm(SchoolScopedModelForm):
    class Meta:
        model = Teacher
        fields = ["name", "weekly_capacity", "lessons", "limit_to_grades", "grades"]
        widgets = {
            "name": forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "نام دبیر"}),
            "weekly_capacity": forms.NumberInput(attrs={"class": BASE_INPUT, "min": 0}),
            "lessons": forms.SelectMultiple(attrs={"class": BASE_SELECT, "size": 8}),
            "limit_to_grades": forms.CheckboxInput(attrs={"class": BASE_CHECK}),
            "grades": forms.SelectMultiple(attrs={"class": BASE_SELECT, "size": 6}),
        }


class TeacherAvailabilityForm(SchoolScopedModelForm):
    class Meta:
        model = TeacherAvailability
        fields = ["teacher", "day", "available_hours"]
        widgets = {
            "teacher": forms.Select(attrs={"class": BASE_SELECT}),
            "day": forms.Select(attrs={"class": BASE_SELECT}),
            "available_hours": forms.NumberInput(attrs={"class": BASE_INPUT, "min": 0}),
        }


class TeachingAssignmentForm(SchoolScopedModelForm):
    class Meta:
        model = TeachingAssignment
        fields = ["teacher"]
        widgets = {"teacher": forms.Select(attrs={"class": BASE_SELECT})}


class TeachingAssignmentItemForm(SchoolScopedModelForm):
    class Meta:
        model = TeachingAssignmentItem
        fields = ["assignment", "school_class", "lesson", "weekly_hours"]
        widgets = {
            "assignment": forms.Select(attrs={"class": BASE_SELECT}),
            "school_class": forms.Select(attrs={"class": BASE_SELECT}),
            "lesson": forms.Select(attrs={"class": BASE_SELECT}),
            "weekly_hours": forms.NumberInput(attrs={"class": BASE_INPUT, "min": 0}),
        }


TeacherAvailabilityFormSet = inlineformset_factory(
    parent_model=Teacher,
    model=TeacherAvailability,
    form=TeacherAvailabilityForm,
    fields=("day", "available_hours"),
    extra=1,
    can_delete=True,
)

TeachingItemInlineFormSet = inlineformset_factory(
    parent_model=TeachingAssignment,
    model=TeachingAssignmentItem,
    form=TeachingAssignmentItemForm,
    fields=("school_class", "lesson", "weekly_hours"),
    extra=1,
    can_delete=True,
)