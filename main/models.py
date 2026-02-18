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
    priority = models.IntegerField(default=1)
    weekly_hours = models.IntegerField(default=2, verbose_name="ساعت در هفته")
    for_all_grades = models.BooleanField(default=False, verbose_name="برای همه پایه‌ها")
    grades = models.ManyToManyField("Grade", blank=True, verbose_name="پایه‌های مرتبط")
    # برای تعیین اینکه درس تک زنگ نباید از هم جدا شود
    allow_split = models.BooleanField(default=False)
    # 🔹 اضافه شدن فیلد جفت شدن با درس‌های دیگر
    paired_lessons = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        verbose_name="درس‌های پیشنهادی برای جفت شدن"
    )
    allow_without_teacher = models.BooleanField(
        default=False,
        verbose_name="میتواند بدون معلم باشد"
    )
    def __str__(self):
        return self.name
class Teacher(models.Model):
    name = models.CharField(max_length=100)

    weekly_capacity = models.IntegerField(
        verbose_name="ظرفیت هفتگی (ساعت)"
    )

    lessons = models.ManyToManyField(
        "Lesson",
        verbose_name="درس‌های قابل تدریس"
    )

    # 🔹 آیا پایه محدود دارد؟
    limit_to_grades = models.BooleanField(
        default=False,
        verbose_name="محدود به پایه خاص"
    )

    # 🔹 اگر محدود باشد این‌ها فعال می‌شود
    grades = models.ManyToManyField(
        "Grade",
        blank=True,
        verbose_name="پایه‌های مجاز"
    )

    def __str__(self):
        return self.name

class TeacherAvailability(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    day = models.ForeignKey(SchoolDay, on_delete=models.CASCADE)
    available_hours = models.IntegerField()  # چند ساعت در آن روز در اختیار است

    class Meta:
        unique_together = ('teacher', 'day')

    def __str__(self):
        return f"{self.teacher.name} - {self.day.name} ({self.available_hours} ساعت)"

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
    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.CASCADE,
        db_index=True
    )

    day_period = models.ForeignKey(
        DayPeriod,
        on_delete=models.CASCADE,
        db_index=True
    )

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,  # مهم
        null=True,                  # اجازه None
        blank=True,
        db_index=True
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        db_index=True
    )

    class Meta:
        unique_together = [
            ('school_class', 'day_period'),
            ('teacher', 'day_period'),
        ]

    def __str__(self):
        return f"{self.school_class} - {self.day_period}"


