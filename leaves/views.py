from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Faculty

from .forms import FacultyLeaveForm
from .models import FacultyLeave


@login_required
def my_leaves(request):
    try:
        faculty = request.user.faculty_profile
    except Faculty.DoesNotExist:  # type: ignore[attr-defined]
        messages.error(request, "You do not have a faculty profile configured.")
        return redirect("accounts:dashboard")

    leaves = FacultyLeave.objects.filter(faculty=faculty).order_by("-start_date")
    return render(request, "leaves/my_leaves.html", {"leaves": leaves})


@login_required
def apply_leave(request):
    try:
        faculty = request.user.faculty_profile
    except Faculty.DoesNotExist:  # type: ignore[attr-defined]
        messages.error(request, "You do not have a faculty profile configured.")
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = FacultyLeaveForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.faculty = faculty
            leave.status = FacultyLeave.PENDING
            leave.save()
            messages.success(request, "Leave request submitted and pending approval.")
            return redirect("leaves:my_leaves")
    else:
        form = FacultyLeaveForm()

    return render(request, "leaves/apply_leave.html", {"form": form})


@staff_member_required
def leave_requests_admin(request):
    leaves = (
        FacultyLeave.objects.select_related("faculty__user")
        .order_by("-start_date")
    )
    return render(request, "leaves/leave_requests_admin.html", {"leaves": leaves})


@staff_member_required
def approve_leave(request, pk):
    leave = get_object_or_404(FacultyLeave, pk=pk)
    leave.status = FacultyLeave.APPROVED
    leave.save(update_fields=["status"])
    messages.success(request, "Leave approved.")
    return redirect("leaves:leave_requests_admin")


@staff_member_required
def reject_leave(request, pk):
    leave = get_object_or_404(FacultyLeave, pk=pk)
    leave.status = FacultyLeave.REJECTED
    leave.save(update_fields=["status"])
    messages.success(request, "Leave rejected.")
    return redirect("leaves:leave_requests_admin")

