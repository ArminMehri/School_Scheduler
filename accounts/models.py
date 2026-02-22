from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    full_name = models.CharField(max_length=200, blank=True)

    school = models.ForeignKey(
        "main.School",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="users"
    )