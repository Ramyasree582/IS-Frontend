from django.contrib import admin

from .models import Faculty


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "get_name", "department", "cabin_block", "cabin_room", "is_active")
    list_filter = ("department", "cabin_block", "is_active")
    search_fields = ("employee_id", "user__username", "user__first_name", "user__last_name")

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    get_name.short_description = "Name"

