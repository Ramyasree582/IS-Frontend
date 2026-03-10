from django.urls import path
from . import views

app_name = "exams"

urlpatterns = [
    path("admin/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/upload-timetable/", views.upload_exam_timetable, name="upload_exam_timetable"),
    path("admin/allocation-overview/", views.allocation_overview, name="allocation_overview"),
    path("admin/departments/", views.manage_departments, name="manage_departments"),
    path("admin/halls/", views.manage_halls, name="manage_halls"),
    path("admin/blocks/", views.blocks_list, name="blocks_list"),
    path("admin/blocks/<str:block_code>/", views.block_detail, name="block_detail"),
    path("admin/exams/", views.exam_list, name="exam_list"),
    path("admin/exams/<int:pk>/", views.exam_detail, name="exam_detail"),
    path("admin/exams/<int:pk>/assign/", views.configure_exam_halls, name="configure_exam_halls"),
    path("admin/exams/<int:pk>/auto-allocate/", views.auto_allocate_for_exam, name="auto_allocate_for_exam"),
    path("admin/exams/<int:pk>/export/", views.export_exam_allocation_csv, name="export_exam_allocation_csv"),
    path("admin/pending-assignments/", views.pending_assignments, name="pending_assignments"),
    path("faculty/dashboard/", views.faculty_dashboard, name="faculty_dashboard"),
    path("assignments/<int:pk>/confirm/", views.confirm_assignment, name="confirm_assignment"),
    path("assignments/<int:pk>/decline/", views.decline_assignment, name="decline_assignment"),
]
