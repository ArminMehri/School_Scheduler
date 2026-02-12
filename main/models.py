from django.db import models

# Create your models here.
class Grade(models.Model):
    name = models.CharField(max_length=50)  # هفتم، هشتم، نهم

    def __str__(self):
        return self.name
class SchoolClass(models.Model):
    name = models.CharField(max_length=50)  # مثلا 7/1
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, db_index=True)

    def __str__(self):
        return self.name
class SchoolDay(models.Model):
    name = models.CharField(max_length=50)  # شنبه، یکشنبه...
    is_active = models.BooleanField(default=True)  # اگر تعطیل بود False

    def __str__(self):
        return self.name


class DayPeriod(models.Model):
    day = models.ForeignKey(SchoolDay, on_delete=models.CASCADE, db_index=True)
    period_number = models.IntegerField()  # زنگ 1، 2، 3...

    class Meta:
        ordering = ['day', 'period_number']

    def __str__(self):
        return f"{self.day.name} - زنگ {self.period_number}"
class Lesson(models.Model):
    name = models.CharField(max_length=100)
    priority = models.IntegerField(default=1)  # درجه سختی (مثلا 1 تا 5)

    def __str__(self):
        return self.name
class Teacher(models.Model):
    name = models.CharField(max_length=100)
    weekly_capacity = models.IntegerField()  # حداکثر ساعت تدریس در هفته

    def __str__(self):
        return self.name
class TeacherAvailability(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, db_index=True)
    day_periods = models.ManyToManyField(DayPeriod, blank=True)

    def __str__(self):
        # نمایش خلاصه‌ای از همه روزها و زنگ‌ها
        periods = ", ".join([str(dp) for dp in self.day_periods.all()])
        return f"{self.teacher.name}: {periods}"

class TeachingAssignment(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
class TeachingAssignmentItem(models.Model):
    assignment = models.ForeignKey(TeachingAssignment, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    weekly_hours = models.IntegerField()  # هر کلاس/درس جدا

    def __str__(self):
        return f"{self.lesson.name} - {self.school_class.name} ({self.weekly_hours} ساعت)"
class Schedule(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, db_index=True)
    day_period = models.ForeignKey(DayPeriod, on_delete=models.CASCADE, db_index=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, db_index=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, db_index=True)

    class Meta:
        unique_together = [
            ('school_class', 'day_period'),  # کلاس تداخل نداشته باشد
            ('teacher', 'day_period'),       # معلم تداخل نداشته باشد
        ]

    def __str__(self):
        return f"{self.school_class} - {self.day_period}"

