from django import forms
from django.urls import path
from django.shortcuts import redirect
from django.contrib import admin, messages
from .services.scheduler import generate_schedule
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


# -------------------- TeacherAvailability --------------------
class TeacherAvailabilityForm(forms.ModelForm):
    class Meta:
        model = TeacherAvailability
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # نمایش نام معلم همراه با ساعت کاری هفته
        self.fields['teacher'].queryset = Teacher.objects.all()
        self.fields['teacher'].label_from_instance = lambda obj: f"{obj.name} - {obj.weekly_capacity} ساعت/هفته"

class TeacherAvailabilityAdmin(admin.ModelAdmin):
    form = TeacherAvailabilityForm
    list_display = ('teacher', 'get_weekly_capacity', 'display_day_periods')
    filter_horizontal = ('day_periods',)

    def get_weekly_capacity(self, obj):
        return obj.teacher.weekly_capacity
    get_weekly_capacity.short_description = 'ساعت کاری هفته'

    def display_day_periods(self, obj):
        return ", ".join([str(dp) for dp in obj.day_periods.all()])
    display_day_periods.short_description = 'زنگ‌ها / روزها'

# -------------------- TeachingAssignment --------------------
class TeachingAssignmentItemInline(admin.TabularInline):
    model = TeachingAssignmentItem
    extra = 1
    autocomplete_fields = ['school_class', 'lesson']

@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ('teacher',)
    autocomplete_fields = ['teacher']
    inlines = [TeachingAssignmentItemInline]

# -------------------- Admin با search_fields برای autocomplete --------------------
@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    search_fields = ('name',)  # اضافه شد برای autocomplete

# -------------------- Schedule با دکمه تولید برنامه --------------------
@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('school_class', 'day_period', 'lesson', 'teacher')
    change_list_template = "admin/main/schedule/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('build/', self.admin_site.admin_view(self.build_schedule_view), name='schedule-build'),
        ]
        return custom_urls + urls

    def build_schedule_view(self, request):
        try:
            generate_schedule()
            self.message_user(request, "برنامه درسی با موفقیت تولید شد.", level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"خطا در تولید برنامه: {e}", level=messages.ERROR)
        return redirect('admin:main_schedule_changelist')

# -------------------- بقیه مدل‌ها --------------------
admin.site.register(Grade)
admin.site.register(SchoolDay)
admin.site.register(DayPeriod)
admin.site.register(TeacherAvailability, TeacherAvailabilityAdmin)
