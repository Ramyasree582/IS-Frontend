from django.contrib import admin

from .models import FacultyLeave


@admin.register(FacultyLeave)
class FacultyLeaveAdmin(admin.ModelAdmin):
    list_display = ("faculty", "start_date", "end_date", "status", "created_at")
    list_filter = ("status", "start_date")
    search_fields = ("faculty__employee_id", "faculty__user__username")

