from django.urls import path
from . import panel_views as v

urlpatterns = [
    # Auth


    # Dashboard
    path("", v.panel_dashboard, name="panel_dashboard"),

    # Actions
    path("generate/", v.generate_schedule_view, name="generate_schedule"),
    path("schedule/clear/", v.schedule_clear, name="schedule_clear"),
    # Schedule actions
    path("schedule/build/", v.panel_schedule_build, name="panel_schedule_build"),
    path("schedule/clear/", v.panel_schedule_clear, name="panel_schedule_clear"),
    # Exports
    path("export/excel/classes/", v.export_excel_classes, name="export_excel_classes"),
    path("export/excel/teachers/", v.export_excel_teachers, name="export_excel_teachers"),
    path("assignments/auto-assign/", v.assignment_auto_assign, name="assignment_auto_assign"),
    # Grades
    path("grades/", v.grade_list, name="grade_list"),
    path("grades/add/", v.grade_create, name="grade_create"),
    path("grades/<int:pk>/edit/", v.grade_update, name="grade_update"),
    path("grades/<int:pk>/delete/", v.grade_delete, name="grade_delete"),

    # SchoolDays
    path("school-days/", v.schoolday_list, name="schoolday_list"),
    path("school-days/add/", v.schoolday_create, name="schoolday_create"),
    path("school-days/<int:pk>/edit/", v.schoolday_update, name="schoolday_update"),
    path("school-days/<int:pk>/delete/", v.schoolday_delete, name="schoolday_delete"),

    # DayPeriods
    path("day-periods/", v.dayperiod_list, name="dayperiod_list"),
    path("day-periods/add/", v.dayperiod_create, name="dayperiod_create"),
    path("day-periods/<int:pk>/edit/", v.dayperiod_update, name="dayperiod_update"),
    path("day-periods/<int:pk>/delete/", v.dayperiod_delete, name="dayperiod_delete"),

    # SchoolClasses
    path("classes/", v.schoolclass_list, name="schoolclass_list"),
    path("classes/add/", v.schoolclass_create, name="schoolclass_create"),
    path("classes/<int:pk>/edit/", v.schoolclass_update, name="schoolclass_update"),
    path("classes/<int:pk>/delete/", v.schoolclass_delete, name="schoolclass_delete"),

    # Lessons
    path("lessons/", v.lesson_list, name="lesson_list"),
    path("lessons/add/", v.lesson_create, name="lesson_create"),
    path("lessons/<int:pk>/edit/", v.lesson_update, name="lesson_update"),
    path("lessons/<int:pk>/delete/", v.lesson_delete, name="lesson_delete"),

    # Teachers
    path("teachers/", v.teacher_list, name="teacher_list"),
    path("teachers/add/", v.teacher_create, name="teacher_create"),
    path("teachers/<int:pk>/edit/", v.teacher_update, name="teacher_update"),
    path("teachers/<int:pk>/delete/", v.teacher_delete, name="teacher_delete"),

    # TeacherAvailability
    path("availability/", v.availability_list, name="availability_list"),
    path("availability/add/", v.availability_create, name="availability_create"),
    path("availability/<int:pk>/edit/", v.availability_update, name="availability_update"),
    path("availability/<int:pk>/delete/", v.availability_delete, name="availability_delete"),

    # TeachingAssignment
    path("teaching-assignments/", v.assignment_list, name="assignment_list"),
    path("teaching-assignments/add/", v.assignment_create, name="assignment_create"),
    path("teaching-assignments/<int:pk>/edit/", v.assignment_update, name="assignment_update"),
    path("teaching-assignments/<int:pk>/delete/", v.assignment_delete, name="assignment_delete"),

    # TeachingAssignmentItem
    path("teaching-items/", v.item_list, name="item_list"),
    path("teaching-items/add/", v.item_create, name="item_create"),
    path("teaching-items/<int:pk>/edit/", v.item_update, name="item_update"),
    path("teaching-items/<int:pk>/delete/", v.item_delete, name="item_delete"),

    # Schedule list (view)
    path("schedule/", v.schedule_list, name="schedule_list"),
]
