import csv
import io

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Faculty
from leaves.models import FacultyLeave

from .forms import CourseForm, FacultyTimeSlotForm, TimetableUploadForm
from .models import Course, FacultyTimeSlot


@staff_member_required
def upload_timetable(request):
    """Admin view to upload faculty timetables via CSV."""

    if request.method == "POST":
        form = TimetableUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data["file"]
            decoded = file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded))

            created = 0
            for row in reader:
                emp_id = row.get("employee_id", "").strip()
                day = row.get("day", "").strip().upper()[:3]
                start = row.get("start_time", "").strip()
                end = row.get("end_time", "").strip()
                course_code = row.get("course_code", "").strip()
                course_name = row.get("course_name", "").strip()
                year_str = row.get("year", "").strip()
                is_lab_str = row.get("is_lab", "").strip().lower()

                if not (emp_id and day and start and end):
                    continue

                try:
                    faculty = Faculty.objects.get(employee_id=emp_id)
                except Faculty.DoesNotExist:
                    continue

                year_val = int(year_str) if year_str.isdigit() else None

                FacultyTimeSlot.objects.create(
                    faculty=faculty,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                    course_code=course_code,
                    course_name=course_name,
                    year=year_val,
                    is_lab=is_lab_str in {"1", "true", "yes"},
                )
                created += 1

            messages.success(request, f"Uploaded timetable. Created {created} slots.")
            return redirect("exams:admin_dashboard")
    else:
        form = TimetableUploadForm()

    return render(request, "timetable/upload_timetable.html", {"form": form})


@staff_member_required
def manage_courses(request):
    """Admin view to manage subjects/courses per year (used by faculty timetable)."""

    courses = Course.objects.all()

    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Course added/updated.")
            return redirect("timetable:manage_courses")
    else:
        form = CourseForm()

    return render(request, "timetable/manage_courses.html", {"form": form, "courses": courses})


@login_required
def faculty_timetable(request):
    """Faculty view of their own timetable."""

    try:
        faculty = request.user.faculty_profile
    except Faculty.DoesNotExist:  # type: ignore[attr-defined]
        messages.error(request, "You do not have a faculty profile configured.")
        return redirect("accounts:dashboard")

    day_order = Case(
        When(day_of_week="MON", then=0),
        When(day_of_week="TUE", then=1),
        When(day_of_week="WED", then=2),
        When(day_of_week="THU", then=3),
        When(day_of_week="FRI", then=4),
        When(day_of_week="SAT", then=5),
        When(day_of_week="SUN", then=6),
        output_field=IntegerField(),
    )

    slots = (
        FacultyTimeSlot.objects.filter(faculty=faculty)
        .annotate(day_order=day_order)
        .order_by("day_order", "start_time")
    )

    today = timezone.localdate()
    approved_leaves = (
        FacultyLeave.objects.filter(
            faculty=faculty,
            status=FacultyLeave.APPROVED,
            end_date__gte=today,
        )
        .order_by("start_date")
    )

    # Define the fixed days and time slots for the grid view
    days = [
        ("MON", "Monday"),
        ("TUE", "Tuesday"),
        ("WED", "Wednesday"),
        ("THU", "Thursday"),
        ("FRI", "Friday"),
        ("SAT", "Saturday"),
    ]

    time_slots = [
        ("10:30-11:30", "10:30 - 11:30"),
        ("11:30-12:30", "11:30 - 12:30"),
        ("13:30-14:30", "1:30 - 2:30"),
        ("14:30-15:30", "2:30 - 3:30"),
        ("15:30-16:30", "3:30 - 4:30"),
    ]

    # Build a grid mapping day -> slot label -> list of FacultyTimeSlot objects
    grid = {day_code: {key: [] for key, _ in time_slots} for day_code, _ in days}

    for s in slots:
        # Build a key like "HH:MM-HH:MM" from the stored times
        key = f"{s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')}"
        if s.day_of_week in grid and key in grid[s.day_of_week]:
            grid[s.day_of_week][key].append(s)

    context = {
        "days": days,
        "time_slots": time_slots,
        "grid": grid,
        "approved_leaves": approved_leaves,
    }
    return render(request, "timetable/faculty_timetable.html", context)


@login_required
def add_slot(request):
    try:
        faculty = request.user.faculty_profile
    except Faculty.DoesNotExist:  # type: ignore[attr-defined]
        messages.error(request, "You do not have a faculty profile configured.")
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = FacultyTimeSlotForm(request.POST)
        if form.is_valid():
            day = form.cleaned_data["day_of_week"]
            start = form.cleaned_data["start_time"]
            end = form.cleaned_data["end_time"]

            # Prevent overlapping slots for the same faculty and day
            conflict_qs = FacultyTimeSlot.objects.filter(faculty=faculty, day_of_week=day)
            for existing in conflict_qs:
                if existing.start_time < end and start < existing.end_time:
                    form.add_error(
                        None,
                        "This time overlaps with an existing slot on this day ("
                        f"{existing.start_time}–{existing.end_time}).",
                    )
                    break

            if not form.errors:
                slot = form.save(commit=False)
                slot.faculty = faculty
                slot.save()
                messages.success(request, "Time slot added to your timetable.")
                return redirect("timetable:faculty_timetable")
    else:
        form = FacultyTimeSlotForm()

    return render(request, "timetable/add_slot.html", {"form": form})


@login_required
def delete_slot(request, pk):
    try:
        faculty = request.user.faculty_profile
    except Faculty.DoesNotExist:  # type: ignore[attr-defined]
        messages.error(request, "You do not have a faculty profile configured.")
        return redirect("accounts:dashboard")

    slot = get_object_or_404(FacultyTimeSlot, pk=pk, faculty=faculty)
    if request.method == "POST":
        slot.delete()
        messages.success(request, "Time slot removed from your timetable.")
        return redirect("timetable:faculty_timetable")

    return render(request, "timetable/confirm_delete_slot.html", {"slot": slot})

