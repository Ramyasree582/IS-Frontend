from django.contrib import admin

from .models import Department, ExamHall, Exam, ExamSessionHall, InvigilationAssignment


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(ExamHall)
class ExamHallAdmin(admin.ModelAdmin):
    list_display = ("name", "block", "floor", "capacity", "is_active")
    list_filter = ("block", "is_active")
    search_fields = ("name", "block")


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("course_code", "course_name", "department", "exam_date", "start_time", "end_time")
    list_filter = ("department", "exam_type", "exam_date")
    search_fields = ("course_code", "course_name")


@admin.register(ExamSessionHall)
class ExamSessionHallAdmin(admin.ModelAdmin):
    list_display = ("exam", "hall", "required_invigilators")
    list_filter = ("hall__block",)


@admin.register(InvigilationAssignment)
class InvigilationAssignmentAdmin(admin.ModelAdmin):
    list_display = ("exam_session_hall", "faculty", "status", "assigned_at", "confirmed_at")
    list_filter = ("status", "exam_session_hall__exam__exam_date")
    search_fields = ("faculty__user__username", "faculty__employee_id")

