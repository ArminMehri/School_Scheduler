from django.db import models
class announce(models.Model):
    announce_title = models.CharField(max_length=1000, verbose_name="اطلاعیه سایت")
    announce = models.BooleanField(default=False, verbose_name="فعال شدن اطلاعیه سایت")
    announce_img = models.ImageField(blank=True,null=True,upload_to='announce', verbose_name="عکس بنر در صورت نیاز",help_text="مهم :اندازه بنز به ارتفاع 80 پیکسل و طول 1400 پیکسل! رنگ پس زمینه عکس باید زرد روشن باشه")
    announce_link = models.CharField(max_length=1000, verbose_name="لینک صفحه مورد نظر")
    class Meta:
        verbose_name = "اطلاعیه سایت"
        verbose_name_plural = "اطلاعیه سایت"
    def __str__(self):
        return f"{self.announce_title}"

class School(models.Model):
    name = models.CharField(max_length=200, verbose_name="نام مدرسه")
    code = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="کد آموزشگاه")
    education_level = models.CharField(max_length=100, verbose_name="مقطع تحصیلی")

    manager_full_name = models.CharField(max_length=200, verbose_name="نام و نام خانوادگی مدیر")
    manager_mobile = models.CharField(max_length=20, verbose_name="موبایل مدیر")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "مدرسه"
        verbose_name_plural = "مدارس"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Grade(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, db_index=True, related_name="grades")
    name = models.CharField(max_length=50, verbose_name="نام پایه")  # هفتم، هشتم، نهم

    class Meta:
        verbose_name = "پایه"
        verbose_name_plural = "پایه‌ها"
        unique_together = ("school", "name")

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, db_index=True, related_name="classes")
    name = models.CharField(max_length=50, verbose_name="نام کلاس")  # مثلا 701
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, db_index=True, related_name="classes")

    class Meta:
        verbose_name = "کلاس"
        verbose_name_plural = "کلاس‌ها"
        unique_together = ("school", "name")

    def __str__(self):
        return self.name


class SchoolDay(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, db_index=True, related_name="days")
    name = models.CharField(max_length=50, verbose_name="نام روز")  # شنبه، یکشنبه...
    is_active = models.BooleanField(default=True, verbose_name="فعال؟")  # اگر تعطیل بود False

    class Meta:
        verbose_name = "روز"
        verbose_name_plural = "روزها"
        unique_together = ("school", "name")

    def __str__(self):
        return self.name


class DayPeriod(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, db_index=True, related_name="periods")
    day = models.ForeignKey(SchoolDay, on_delete=models.CASCADE, db_index=True, related_name="periods")
    period_number = models.IntegerField(verbose_name="شماره زنگ")  # زنگ 1، 2، 3...

    class Meta:
        verbose_name = "زنگ"
        verbose_name_plural = "زنگ‌ها"
        ordering = ["day", "period_number"]
        unique_together = ("school", "day", "period_number")

    def __str__(self):
        return f"{self.day.name} - زنگ {self.period_number}"


class Lesson(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, db_index=True, related_name="lessons")
    name = models.CharField(max_length=100, verbose_name="نام درس")
    weekly_hours = models.IntegerField(default=2, verbose_name="ساعت در هفته")
    for_all_grades = models.BooleanField(default=False, verbose_name="برای همه پایه‌ها")
    grades = models.ManyToManyField(Grade, blank=True, verbose_name="پایه‌های مرتبط", related_name="lessons")

    allow_split = models.BooleanField(default=False, verbose_name="اجازه جدا شدن (Split)")

    paired_lessons = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        verbose_name="درس‌های پیشنهادی برای جفت شدن",
        related_name="paired_with",
    )

    allow_without_teacher = models.BooleanField(default=False, verbose_name="می‌تواند بدون معلم باشد")

    class Meta:
        verbose_name = "درس"
        verbose_name_plural = "درس‌ها"
        unique_together = ("school", "name")

    def __str__(self):
        return self.name


class Teacher(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, db_index=True, related_name="teachers")
    name = models.CharField(max_length=100, verbose_name="نام دبیر")

    weekly_capacity = models.IntegerField(verbose_name="ظرفیت هفتگی (ساعت)")
    lessons = models.ManyToManyField(Lesson, verbose_name="درس‌های قابل تدریس", related_name="teachers")

    limit_to_grades = models.BooleanField(default=False, verbose_name="محدود به پایه خاص")
    grades = models.ManyToManyField(Grade, blank=True, verbose_name="پایه‌های مجاز", related_name="teachers")

    class Meta:
        verbose_name = "دبیر"
        verbose_name_plural = "دبیرها"
        unique_together = ("school", "name")

    def __str__(self):
        return self.name


class TeacherAvailability(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, db_index=True, related_name="teacher_availabilities")
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="availabilities")
    day = models.ForeignKey(SchoolDay, on_delete=models.CASCADE)
    available_hours = models.IntegerField(verbose_name="ساعت‌های مجاز")

    class Meta:
        verbose_name = "حضور دبیر"
        verbose_name_plural = "حضور دبیرها"
        unique_together = ("school", "teacher", "day")

    def __str__(self):
        return f"{self.teacher.name} - {self.day.name} ({self.available_hours} ساعت)"


class TeachingAssignment(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, db_index=True, related_name="teaching_assignments")
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="assignments")

    class Meta:
        verbose_name = "تخصیص تدریس"
        verbose_name_plural = "تخصیص‌های تدریس"
        unique_together = ("school", "teacher")

    def __str__(self):
        return f"{self.teacher.name}"


class TeachingAssignmentItem(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, db_index=True, related_name="teaching_items")
    assignment = models.ForeignKey(TeachingAssignment, on_delete=models.CASCADE, related_name="items")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="teaching_items")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="teaching_items")
    weekly_hours = models.IntegerField(verbose_name="ساعت هفتگی")

    class Meta:
        verbose_name = "آیتم تدریس"
        verbose_name_plural = "آیتم‌های تدریس"
        unique_together = ("school", "assignment", "school_class", "lesson")

    def __str__(self):
        return f"{self.lesson.name} - {self.school_class.name} ({self.weekly_hours} ساعت)"


class Schedule(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, db_index=True, related_name="schedules")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, db_index=True)
    day_period = models.ForeignKey(DayPeriod, on_delete=models.CASCADE, db_index=True)

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
    )

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, db_index=True)

    class Meta:
        verbose_name = "برنامه"
        verbose_name_plural = "برنامه‌ها"
        unique_together = [
            ("school", "school_class", "day_period"),
            ("school", "teacher", "day_period"),
        ]

    def __str__(self):
        return f"{self.school_class} - {self.day_period}"

class ScheduleBuildProgress(models.Model):
    school = models.OneToOneField(School, on_delete=models.CASCADE)
    percent = models.IntegerField(default=0)
    status = models.CharField(max_length=100, default="در انتظار...")
    updated_at = models.DateTimeField(auto_now=True)