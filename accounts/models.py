# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    # اگر فعلاً فقط می‌خوای آماده باشه:
    phone = models.CharField(max_length=20, blank=True)
    # بعداً می‌تونیم school را هم اینجا اضافه کنیم یا جداگانه پروفایل بسازیم
    # school = models.ForeignKey("main.School", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.username