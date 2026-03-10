from django.db import models


class Course(models.Model):
    YEAR_CHOICES = [(1, "1"), (2, "2"), (3, "3"), (4, "4")]

    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)

    class Meta:
        unique_together = ("code", "year")
        ordering = ["year", "code"]

    def __str__(self) -> str:
        return f"Y{self.year} - {self.code} {self.name}"


class FacultyTimeSlot(models.Model):
    MONDAY = 'MON'
    TUESDAY = 'TUE'
    WEDNESDAY = 'WED'
    THURSDAY = 'THU'
    FRIDAY = 'FRI'
    SATURDAY = 'SAT'
    SUNDAY = 'SUN'

    DAY_CHOICES = [
        (MONDAY, 'Monday'),
        (TUESDAY, 'Tuesday'),
        (WEDNESDAY, 'Wednesday'),
        (THURSDAY, 'Thursday'),
        (FRIDAY, 'Friday'),
        (SATURDAY, 'Saturday'),
        (SUNDAY, 'Sunday'),
    ]

    faculty = models.ForeignKey('accounts.Faculty', on_delete=models.CASCADE, related_name='timetable_slots')
    day_of_week = models.CharField(max_length=3, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    course_code = models.CharField(max_length=20, blank=True)
    course_name = models.CharField(max_length=200, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Year of study (1-4)")
    is_lab = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.faculty} - {self.day_of_week} {self.start_time}-{self.end_time}"

