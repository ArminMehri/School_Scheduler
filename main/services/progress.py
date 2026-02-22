from main.models import ScheduleBuildProgress

def update_progress(school, percent: int, status: str):
    obj, _ = ScheduleBuildProgress.objects.get_or_create(school=school)
    obj.percent = int(percent)
    obj.status = status
    obj.save(update_fields=["percent", "status", "updated_at"])