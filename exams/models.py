from django.db import models
from django.conf import settings


class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ExamHall(models.Model):
    name = models.CharField(max_length=50)
    block = models.CharField(max_length=50)
    floor = models.CharField(max_length=20, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.block})"


class Exam(models.Model):
    MID = 'MID'
    END = 'END'
    TEST = 'TEST'

    EXAM_TYPE_CHOICES = [
        (MID, 'Mid-term'),
        (END, 'End-semester'),
        (TEST, 'Test'),
    ]

    course_code = models.CharField(max_length=20)
    course_name = models.CharField(max_length=200)
    exam_type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='exams')
    year = models.PositiveSmallIntegerField(help_text="Year of study (1-4)")
    semester = models.PositiveSmallIntegerField()
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.course_code} - {self.exam_date}"


class ExamSessionHall(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='session_halls')
    hall = models.ForeignKey(ExamHall, on_delete=models.CASCADE, related_name='exam_sessions')
    required_invigilators = models.PositiveIntegerField(default=1)

    def __str__(self) -> str:
        return f"{self.exam} @ {self.hall}"


class InvigilationAssignment(models.Model):
    PENDING_CONFIRMATION = 'PENDING_CONFIRMATION'
    CONFIRMED = 'CONFIRMED'
    DECLINED = 'DECLINED'
    CANCELLED = 'CANCELLED'
    REASSIGNED = 'REASSIGNED'

    STATUS_CHOICES = [
        (PENDING_CONFIRMATION, 'Pending Confirmation'),
        (CONFIRMED, 'Confirmed'),
        (DECLINED, 'Declined'),
        (CANCELLED, 'Cancelled'),
        (REASSIGNED, 'Reassigned'),
    ]

    exam_session_hall = models.ForeignKey(ExamSessionHall, on_delete=models.CASCADE, related_name='assignments')
    faculty = models.ForeignKey('accounts.Faculty', on_delete=models.CASCADE, related_name='invigilation_assignments')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=PENDING_CONFIRMATION)
    assigned_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    confirmation_deadline = models.DateTimeField(null=True, blank=True)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.exam_session_hall} -> {self.faculty} ({self.status})"

