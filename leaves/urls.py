from django.urls import path

from . import views

app_name = "leaves"

urlpatterns = [
    path("faculty/", views.my_leaves, name="my_leaves"),
    path("faculty/apply/", views.apply_leave, name="apply_leave"),
    path("admin/", views.leave_requests_admin, name="leave_requests_admin"),
    path("admin/<int:pk>/approve/", views.approve_leave, name="approve_leave"),
    path("admin/<int:pk>/reject/", views.reject_leave, name="reject_leave"),
]
