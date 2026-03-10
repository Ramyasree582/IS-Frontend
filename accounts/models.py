from django.db import models
from django.conf import settings


class Faculty(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='faculty_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey('exams.Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='faculty')
    cabin_block = models.CharField(max_length=50, blank=True)
    cabin_room = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.user.get_full_name() or self.user.username} ({self.employee_id})"


class LoginOTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='login_otps')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"OTP for {self.user} ({self.code})"


