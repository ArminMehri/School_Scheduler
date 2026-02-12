from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from main.models import Schedule
from main.services.validator import run_full_validation
from main.services.scheduler import generate_schedule


def schedule_table(request):
    schedules = (
        Schedule.objects
        .select_related(
            'school_class',
            'school_class__grade',
            'day_period',
            'day_period__day',
            'lesson',
            'teacher'
        )
        .order_by(
            'school_class__grade__id',
            'school_class__name',
            'day_period__day__id',
            'day_period__period_number'
        )
    )

    context = {
        "data_table": schedules
    }

    return render(request, "schedule_table.html", context)


@require_POST
def build_schedule(request):
    # اجرای اعتبارسنجی قبل از تولید برنامه
    errors = run_full_validation()

    if errors:
        return JsonResponse({
            "status": "error",
            "errors": errors
        }, status=400)

    try:
        generate_schedule()
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "errors": [str(e)]
        }, status=500)

    return JsonResponse({
        "status": "success",
        "message": "برنامه با موفقیت تولید شد"
    })
