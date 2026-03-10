from django.urls import path

from . import views

app_name = "timetable"

urlpatterns = [
    path("admin/upload/", views.upload_timetable, name="upload_timetable"),
    path("admin/courses/", views.manage_courses, name="manage_courses"),
    path("faculty/", views.faculty_timetable, name="faculty_timetable"),
    path("faculty/add/", views.add_slot, name="add_slot"),
    path("faculty/slot/<int:pk>/delete/", views.delete_slot, name="delete_slot"),
]
