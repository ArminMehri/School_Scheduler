from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from django.utils.html import format_html
from .services.scheduler import generate_schedule
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
    list_display = ('name', 'priority','weekly_hours')
    search_fields = ('name',)


# ============================================================
# TeachingAssignment
# ============================================================

class TeachingAssignmentItemInline(admin.TabularInline):
    model = TeachingAssignmentItem
    extra = 1
    autocomplete_fields = ('school_class', 'lesson')


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ('teacher',)
    autocomplete_fields = ('teacher',)
    inlines = [TeachingAssignmentItemInline]

    # دکمه Auto Assign
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'auto-assign/',
                self.admin_site.admin_view(self.auto_assign_view),
                name='auto-assign',
            ),
        ]
        return custom_urls + urls

    def auto_assign_view(self, request):
        try:
            auto_assign_teachers()
            self.message_user(
                request,
                "تخصیص خودکار معلم‌ها با موفقیت انجام شد.",
                level=messages.SUCCESS,
            )
        except Exception as e:
            self.message_user(
                request,
                f"خطا در تخصیص خودکار: {e}",
                level=messages.ERROR,
            )

        return redirect('admin:main_teachingassignment_changelist')


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
        from .models import TeachingAssignmentItem

        try:
            # اگر هیچ assignment وجود نداشت → اول auto assign
            if not TeachingAssignmentItem.objects.exists():
                auto_assign_teachers()

            generate_schedule()

            self.message_user(
                request,
                "برنامه درسی با موفقیت تولید شد.",
                level=messages.SUCCESS,
            )

        except Exception as e:
            self.message_user(
                request,
                f"خطا در تولید برنامه: {e}",
                level=messages.ERROR,
            )

        return redirect('admin:main_schedule_changelist')


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
