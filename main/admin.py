from . import models
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from django.utils.html import format_html
from .solver_engine import generate_schedule_with_ortools
import traceback
from .services.auto_assign import auto_assign_teachers

from .models import (
    Grade,
    SchoolClass,
    SchoolDay,
    DayPeriod,
    Lesson,
    Teacher,
    TeacherAvailability,
    TeachingAssignment,
    TeachingAssignmentItem,
    Schedule,
)
admin.site.register(models.announce)
# ============================================================
# Teacher + Availability (Inline)
# ============================================================

class TeacherAvailabilityInline(admin.TabularInline):
    model = TeacherAvailability
    extra = 1
    fields = ('day', 'available_hours')


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('name', 'weekly_capacity', 'limit_to_grades')
    search_fields = ('name',)
    filter_horizontal = ('lessons', 'grades')
    inlines = [TeacherAvailabilityInline]


# ============================================================
# SchoolClass
# ============================================================

@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'grade')
    search_fields = ('name',)


# ============================================================
# Lesson
# ============================================================

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('name', 'weekly_hours', 'for_all_grades', 'allow_without_teacher')
    search_fields = ('name',)
    filter_horizontal = ('grades', 'paired_lessons')


# ============================================================
# TeachingAssignmentItem (صفحه مستقل با فیلتر)
# ============================================================

@admin.register(TeachingAssignmentItem)
class TeachingAssignmentItemAdmin(admin.ModelAdmin):
    list_display = (
        "school_class",
        "lesson",
        "weekly_hours",
        "assignment",
        "school",
    )
    list_filter = ("school_class", "lesson","school",)
    search_fields = (
        "school_class__name",
        "lesson__name",
        "assignment__teacher__name",  # برای autocomplete امن
    )
    autocomplete_fields = (
        "school_class",
        "lesson",
        "assignment",
    )


# ============================================================
# TeachingAssignment Inline
# ============================================================

class TeachingAssignmentItemInline(admin.TabularInline):
    model = TeachingAssignmentItem
    extra = 1
    autocomplete_fields = ('school_class', 'lesson')


# ============================================================
# TeachingAssignment
# ============================================================

@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'assigned_classes_info',"school",)
    list_filter = ("school",)
    search_fields = ('teacher__name',)
    inlines = [TeachingAssignmentItemInline]

    def assigned_classes_info(self, obj):
        """
        نمایش لیست کلاس‌ها و درس‌های هر کلاس به همراه ساعت درسی
        """
        assignments = TeachingAssignmentItem.objects.filter(assignment=obj)
        class_dict = {}
        for item in assignments:
            cls_name = item.school_class.name
            if cls_name not in class_dict:
                class_dict[cls_name] = []
            class_dict[cls_name].append(f"{item.lesson.name} ({item.weekly_hours} زنگ)")

        html = ""
        for cls, lessons in class_dict.items():
            html += f"<b>{cls}:</b> " + ", ".join(lessons) + "<br>"

        return format_html(html)

    assigned_classes_info.short_description = "کلاس‌ها و درس‌ها"


# ============================================================
# Schedule
# ============================================================

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('school_class', 'day_period', 'lesson', 'colored_teacher')
    list_filter = ('school_class', 'day_period__day')
    search_fields = ('school_class__name', 'lesson__name', 'teacher__name')
    change_list_template = "admin/main/schedule/change_list.html"

    def colored_teacher(self, obj):
        if obj.teacher:
            return obj.teacher.name
        return format_html(
            '<span style="color:red; font-weight:bold;">بدون دبیر</span>'
        )

    colored_teacher.short_description = "دبیر"

    # دکمه Generate Schedule
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'build/',
                self.admin_site.admin_view(self.build_schedule_view),
                name='schedule-build',
            ),
        ]
        return custom_urls + urls


    def build_schedule_view(self, request):
        school = getattr(request.user, "school", None)
        if school is None:
            messages.error(request, "❌ این حساب به هیچ مدرسه‌ای وصل نیست.")
            return redirect("..")

        try:
            generate_schedule_with_ortools(school=school)
            messages.success(request, "✅ برنامه برای همین مدرسه ساخته شد.")

        except Exception as e:
            # 🔴 لاگ کامل در ترمینال
            print("\n" + "=" * 80)
            print("❌ ERROR WHILE GENERATING SCHEDULE")
            print(f"School: {school} (id={school.id})")
            print("-" * 80)
            traceback.print_exc()  # 👈 مهم‌ترین خط
            print("=" * 80 + "\n")

            # 🟡 پیام خلاصه برای UI
            messages.error(request, f"❌ خطا در تولید برنامه: {e}")

        return redirect("..")


# ============================================================
# سایر مدل‌ها
# ============================================================

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    search_fields = ('name',)


@admin.register(SchoolDay)
class SchoolDayAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')


@admin.register(DayPeriod)
class DayPeriodAdmin(admin.ModelAdmin):
    list_display = ('day', 'period_number')
    list_filter = ('day',)
admin.site.register(models.School)