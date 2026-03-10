from django.contrib import admin

from .models import FacultyTimeSlot


@admin.register(FacultyTimeSlot)
class FacultyTimeSlotAdmin(admin.ModelAdmin):
    list_display = ("faculty", "day_of_week", "start_time", "end_time", "course_code", "course_name")
    list_filter = ("day_of_week", "faculty__department")
    search_fields = ("faculty__employee_id", "course_code", "course_name")

