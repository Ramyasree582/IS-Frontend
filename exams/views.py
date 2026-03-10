from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Prefetch
from .models import Exam, Department, ExamSessionHall, InvigilationAssignment
from accounts.models import Faculty
from leaves.models import FacultyLeave
from timetable.models import FacultyTimeSlot
from .forms import ExamTimetableUploadForm
from datetime import datetime, timedelta
import csv

User = get_user_model()

from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Faculty
from leaves.models import FacultyLeave
from timetable.models import FacultyTimeSlot

from .forms import ExamTimetableUploadForm
from .models import Department, Exam, ExamHall, ExamSessionHall, InvigilationAssignment


@staff_member_required
def admin_dashboard(request):
    # Ensure default departments exist
    if not Department.objects.exists():
        Department.objects.bulk_create(
            [
                Department(code="CSE", name="Computer Science and Engineering"),
                Department(code="CSM", name="Computer Science and AI/ML"),
                Department(code="CSD", name="Computer Science and Data Science"),
                Department(code="ECE", name="Electronics and Communication Engineering"),
                Department(code="EEE", name="Electrical and Electronics Engineering"),
                Department(code="MECH", name="Mechanical Engineering"),
                Department(code="CIVIL", name="Civil Engineering"),
            ]
        )

    today = timezone.localdate()
    upcoming_exams = Exam.objects.filter(exam_date__gte=today).order_by("exam_date", "start_time")[:10]

    pending_assignments = InvigilationAssignment.objects.filter(
        status=InvigilationAssignment.PENDING_CONFIRMATION
    ).select_related("exam_session_hall__exam")

    context = {
        "upcoming_exams_count": Exam.objects.filter(exam_date__gte=today).count(),
        "today_exams_count": Exam.objects.filter(exam_date=today).count(),
        "pending_assignments_count": pending_assignments.count(),
        "upcoming_exams": upcoming_exams,
        "total_faculty_count": Faculty.objects.filter(is_active=True).count(),
    }
    return render(request, "exams/admin_dashboard.html", context)


@staff_member_required
def upload_exam_timetable(request):
    """Upload exam timetable (exam schedule) via CSV."""

    if request.method == "POST":
        form = ExamTimetableUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data["file"]
            decoded = file.read().decode("utf-8")
            reader = csv.DictReader(decoded.splitlines())

            created = 0
            for row in reader:
                dept_code = row.get("department_code", "").strip().upper()
                course_code = row.get("course_code", "").strip()
                course_name = row.get("course_name", "").strip()
                exam_type = row.get("exam_type", "").strip().upper() or Exam.TEST
                year = row.get("year", "").strip()
                semester = row.get("semester", "").strip()
                exam_date = row.get("exam_date", "").strip()
                start_time = row.get("start_time", "").strip()
                end_time = row.get("end_time", "").strip()

                if not (dept_code and course_code and exam_date and start_time and end_time and year and semester):
                    continue

                try:
                    department = Department.objects.get(code=dept_code)
                except Department.DoesNotExist:
                    continue

                Exam.objects.create(
                    course_code=course_code,
                    course_name=course_name or course_code,
                    exam_type=exam_type,
                    department=department,
                    year=int(year),
                    semester=int(semester),
                    exam_date=exam_date,
                    start_time=start_time,
                    end_time=end_time,
                    created_by=request.user,
                )
                created += 1

            messages.success(request, f"Exam timetable uploaded. Created {created} exams.")
            return redirect("exams:exam_list")
    else:
        form = ExamTimetableUploadForm()

    return render(request, "exams/upload_exam_timetable.html", {"form": form})


@staff_member_required
def allocation_overview(request):
    """Block-wise overview of invigilation allocations for admins."""

    date_str = request.GET.get("date")
    block = request.GET.get("block", "").strip()

    assignments = (
        InvigilationAssignment.objects.select_related(
            "exam_session_hall__exam",
            "exam_session_hall__hall",
            "faculty__user",
            "faculty__department",
        )
        .filter(status__in=[
            InvigilationAssignment.PENDING_CONFIRMATION,
            InvigilationAssignment.CONFIRMED,
        ])
    )

    if date_str:
        try:
            filter_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            assignments = assignments.filter(exam_session_hall__exam__exam_date=filter_date)
        except ValueError:
            date_str = ""

    if block:
        assignments = assignments.filter(exam_session_hall__hall__block__iexact=block)

    assignments = assignments.order_by(
        "exam_session_hall__exam__exam_date",
        "exam_session_hall__hall__block",
        "exam_session_hall__hall__name",
        "faculty__department__code",
        "faculty__user__last_name",
    )

    # Collect distinct dates and blocks for filter dropdowns
    dates = (
        Exam.objects.order_by("exam_date")
        .values_list("exam_date", flat=True)
        .distinct()
    )
    blocks = (
        ExamSessionHall.objects.select_related("hall")
        .values_list("hall__block", flat=True)
        .distinct()
    )

    context = {
        "assignments": assignments,
        "filter_date": date_str or "",
        "filter_block": block,
        "dates": dates,
        "blocks": blocks,
    }
    return render(request, "exams/allocation_overview.html", context)


@staff_member_required
def manage_departments(request):
    """Simple UI for platform admin to view/add/delete departments."""

    if request.method == "POST":
        # Add new department
        code = request.POST.get("code", "").strip().upper()
        name = request.POST.get("name", "").strip()
        delete_id = request.POST.get("delete_id")

        if delete_id:
            Department.objects.filter(id=delete_id).delete()
        elif code and name:
            Department.objects.get_or_create(code=code, defaults={"name": name})

        return redirect("exams:manage_departments")

    departments = Department.objects.all().order_by("code")
    return render(request, "exams/manage_departments.html", {"departments": departments})


@staff_member_required
def manage_halls(request):
    """Simple UI for platform admin to add/delete exam halls (blocks / rooms)."""

    if request.method == "POST":
        delete_id = request.POST.get("delete_id")
        if delete_id:
            ExamHall.objects.filter(id=delete_id).delete()
            return redirect("exams:manage_halls")

        name = request.POST.get("name", "").strip()
        block = request.POST.get("block", "").strip()
        floor = request.POST.get("floor", "").strip()
        capacity = request.POST.get("capacity", "").strip()

        if name and block:
            try:
                cap_val = int(capacity) if capacity else 0
            except ValueError:
                cap_val = 0
            ExamHall.objects.create(
                name=name,
                block=block,
                floor=floor,
                capacity=cap_val,
                is_active=True,
            )
            messages.success(request, "Hall/room added.")
            return redirect("exams:manage_halls")

    # Order by block, then floor (G/0,1,2,...) and then name
    floor_order = ["G", "GROUND", "0", "1", "2", "3"]
    def floor_key(h):
        f = (h.floor or "").upper()
        try:
            idx = floor_order.index(f)
        except ValueError:
            idx = len(floor_order)
        return (h.block, idx, h.name)

    halls = sorted(ExamHall.objects.all(), key=floor_key)
    return render(request, "exams/manage_halls.html", {"halls": halls})


@staff_member_required
def blocks_list(request):
    """List distinct blocks; clicking a block shows its rooms."""

    blocks = (
        ExamHall.objects.values_list("block", flat=True)
        .distinct()
        .order_by("block")
    )
    return render(request, "exams/blocks_list.html", {"blocks": blocks})


@staff_member_required
def block_detail(request, block_code):
    """Show rooms for a single block, ordered by floor, with faculty cabins info."""

    block_code = block_code.strip()
    halls_qs = ExamHall.objects.filter(block=block_code)

    floor_order = ["G", "GROUND", "0", "1", "2", "3"]

    def floor_key(h):
        f = (h.floor or "").upper()
        try:
            idx = floor_order.index(f)
        except ValueError:
            idx = len(floor_order)
        return (idx, h.name)

    halls = sorted(halls_qs, key=floor_key)

    # Map room name -> list of faculty names for cabins in this block/room
    room_names = [h.name for h in halls]
    faculty_qs = Faculty.objects.filter(cabin_block=block_code, cabin_room__in=room_names).select_related("user")
    faculty_by_room = {}
    for f in faculty_qs:
        key = f.cabin_room
        faculty_by_room.setdefault(key, []).append(f.user.get_full_name() or f.user.username)

    return render(
        request,
        "exams/block_detail.html",
        {"block_code": block_code, "halls": halls, "faculty_by_room": faculty_by_room},
    )


@staff_member_required
def exam_list(request):
    exams = Exam.objects.select_related("department").order_by("exam_date", "start_time")
    return render(request, "exams/exam_list.html", {"exams": exams})


@staff_member_required
def exam_detail(request, pk):
    exam = get_object_or_404(Exam.objects.select_related("department"), pk=pk)
    session_halls = (
        ExamSessionHall.objects.filter(exam=exam)
        .select_related("hall")
        .prefetch_related(
            Prefetch(
                "assignments",
                queryset=InvigilationAssignment.objects.select_related("faculty__user", "faculty__department"),
            )
        )
        .order_by("hall__block", "hall__floor", "hall__name")
    )

    # Build assignments_by_hall for quick lookup
    assignments_by_hall = {}
    for session in session_halls:
        assignments_by_hall.setdefault(session.hall, list(session.assignments.all()))

    has_assignments = InvigilationAssignment.objects.filter(exam_session_hall__exam=exam).exists()

    context = {
        "exam": exam,
        "session_halls": session_halls,
        "assignments_by_hall": assignments_by_hall,
        "has_assignments": has_assignments,
    }
    return render(request, "exams/exam_detail.html", context)


@staff_member_required
def configure_exam_halls(request, pk):
    """Step before auto-allocation: choose block and rooms (halls) for this exam.

    Admin selects a block and then marks which rooms in that block are available
    for this exam. We create ExamSessionHall entries accordingly and then run
    the existing auto-allocation logic.
    """

    exam = get_object_or_404(Exam, pk=pk)

    # Preload all halls grouped by block so admin can select rooms from
    # multiple blocks for the same examination in one step.
    blocks = (
        ExamHall.objects.values_list("block", flat=True)
        .distinct()
        .order_by("block")
    )
    halls_by_block = {}
    floor_order = ["G", "GROUND", "0", "1", "2", "3"]

    def floor_key(h):
        f = (h.floor or "").upper()
        try:
            idx = floor_order.index(f)
        except ValueError:
            idx = len(floor_order)
        return (idx, h.name)

    for b in blocks:
        qs = ExamHall.objects.filter(block=b)
        halls_by_block[b] = sorted(qs, key=floor_key)

    if request.method == "POST":
        hall_ids = request.POST.getlist("hall_ids")

        # Clear previous room mappings for this exam
        ExamSessionHall.objects.filter(exam=exam).delete()

        for hid in hall_ids:
            try:
                hall = ExamHall.objects.get(id=hid)
            except ExamHall.DoesNotExist:
                continue
            # Read required invigilators per room (default to 1)
            req_key = f"req_{hid}"
            required = int(request.POST.get(req_key, "1"))
            ExamSessionHall.objects.create(exam=exam, hall=hall, required_invigilators=required)

        if hall_ids:
            messages.success(request, "Rooms selected for this exam. Auto-allocating duties now.")
            return redirect("exams:auto_allocate_for_exam", pk=exam.pk)
        else:
            messages.warning(request, "No rooms selected. Please choose at least one room.")

    context = {
        "exam": exam,
        "blocks": blocks,
        "halls_by_block": halls_by_block,
    }
    return render(request, "exams/configure_exam_halls.html", context)


def _faculty_has_clash(faculty, exam):
    exam_start = datetime.combine(exam.exam_date, exam.start_time)
    exam_end = datetime.combine(exam.exam_date, exam.end_time)

    weekday = exam.exam_date.strftime("%a").upper()[:3]

    slots = FacultyTimeSlot.objects.filter(faculty=faculty, day_of_week=weekday)
    for slot in slots:
        # If this teaching slot is for the same student year as the exam,
        # we assume that class is cancelled because of the exam, so it
        # does NOT block invigilation duties.
        if slot.year and slot.year == exam.year:
            continue
        slot_start = datetime.combine(exam.exam_date, slot.start_time)
        slot_end = datetime.combine(exam.exam_date, slot.end_time)
        if slot_start < exam_end and exam_start < slot_end:
            return True
    return False


def _faculty_on_approved_leave(faculty, exam_date):
    return FacultyLeave.objects.filter(
        faculty=faculty,
        status=FacultyLeave.APPROVED,
        start_date__lte=exam_date,
        end_date__gte=exam_date,
    ).exists()


@staff_member_required
def auto_allocate_for_exam(request, pk):
    exam = get_object_or_404(Exam.objects.select_related("department"), pk=pk)
    session_halls = ExamSessionHall.objects.filter(exam=exam).select_related("hall")

    if not session_halls.exists():
        messages.warning(request, "No halls/rooms are configured for this exam. Please use 'Assign Duties (Select Rooms)' first.")
        return redirect("exams:exam_detail", pk=exam.pk)

    all_faculty = (
        Faculty.objects.filter(is_active=True)
        .exclude(department=exam.department)
        .select_related("department", "user")
    )

    # Track faculty already assigned anywhere for this exam to avoid multiple halls
    global_assigned_ids = set(
        InvigilationAssignment.objects.filter(exam_session_hall__exam=exam).values_list("faculty_id", flat=True)
    )

    for session in session_halls:
        required = session.required_invigilators
        if required <= 0:
            continue

        current_assignments = InvigilationAssignment.objects.filter(exam_session_hall=session)
        already_assigned_ids = set(current_assignments.values_list("faculty_id", flat=True)) | global_assigned_ids

        # Debug counters
        excluded_dept = 0
        excluded_assigned = 0
        excluded_leave = 0
        excluded_clash = 0

        eligible = []
        for faculty in all_faculty:
            # Exclude same department (already done in query, but count for debug)
            if faculty.department == exam.department:
                excluded_dept += 1
                continue
            if faculty.id in already_assigned_ids:
                excluded_assigned += 1
                continue
            if _faculty_on_approved_leave(faculty, exam.exam_date):
                excluded_leave += 1
                continue
            if _faculty_has_clash(faculty, exam):
                excluded_clash += 1
                continue
            eligible.append(faculty)

        scored = []
        for faculty in eligible:
            score = 0
            if faculty.cabin_block and faculty.cabin_block == session.hall.block:
                score += 10
            load = InvigilationAssignment.objects.filter(faculty=faculty).count()
            scored.append((score, load, faculty))

        scored.sort(key=lambda item: (-item[0], item[1]))

        chosen = [faculty for _, _, faculty in scored[:required]]

        for faculty in chosen:
            assignment, created = InvigilationAssignment.objects.get_or_create(
                exam_session_hall=session,
                faculty=faculty,
                defaults={
                    "status": InvigilationAssignment.PENDING_CONFIRMATION,
                },
            )
            if created:
                global_assigned_ids.add(faculty.id)
                exam_start_dt = datetime.combine(exam.exam_date, exam.start_time)
                deadline = timezone.make_aware(exam_start_dt) - timedelta(hours=1, minutes=30)
                assignment.confirmation_deadline = deadline
                assignment.notification_sent_at = timezone.now()
                assignment.save(update_fields=["confirmation_deadline", "notification_sent_at"])

        # Debug info for this session
        messages.info(
            request,
            f"Session {session.hall.name}: {len(eligible)} eligible, {len(chosen)} assigned (required {required}). "
            f"Excluded: dept={excluded_dept}, assigned={excluded_assigned}, leave={excluded_leave}, clash={excluded_clash}."
        )

    messages.success(request, "Invigilation duties have been auto-allocated for this exam where possible.")
    return redirect("exams:exam_detail", pk=exam.pk)


@staff_member_required
def export_exam_allocation_csv(request, pk):
    """Export allocation details for a specific exam as CSV."""

    exam = get_object_or_404(Exam.objects.select_related("department"), pk=pk)
    assignments = (
        InvigilationAssignment.objects.filter(exam_session_hall__exam=exam)
        .select_related(
            "exam_session_hall__exam",
            "exam_session_hall__hall",
            "faculty__user",
            "faculty__department",
        )
        .order_by("exam_session_hall__hall__block", "exam_session_hall__hall__name")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename=exam_{exam.id}_allocation.csv"

    writer = csv.writer(response)
    writer.writerow([
        "exam_date",
        "start_time",
        "end_time",
        "course_code",
        "course_name",
        "department",
        "hall_block",
        "hall_name",
        "hall_capacity",
        "required_invigilators",
        "faculty_employee_id",
        "faculty_name",
        "faculty_email",
        "faculty_department",
        "status",
        "assigned_at",
        "confirmed_at",
        "declined_at",
    ])
    for a in assignments:
        writer.writerow([
            exam.exam_date,
            exam.start_time,
            exam.end_time,
            exam.course_code,
            exam.course_name,
            exam.department.code,
            a.exam_session_hall.hall.block,
            a.exam_session_hall.hall.name,
            a.exam_session_hall.hall.capacity,
            a.exam_session_hall.required_invigilators,
            a.faculty.employee_id,
            a.faculty.user.get_full_name(),
            a.faculty.user.email,
            a.faculty.department.code,
            a.status,
            a.assigned_at,
            a.confirmed_at,
            a.declined_at,
        ])
    return response


@staff_member_required
def pending_assignments(request):
    """List all pending invigilation assignments with Approve/Decline actions."""
    assignments = (
        InvigilationAssignment.objects.filter(status=InvigilationAssignment.PENDING_CONFIRMATION)
        .select_related(
            "exam_session_hall__exam",
            "exam_session_hall__hall",
            "faculty__user",
            "faculty__department",
        )
        .order_by("confirmation_deadline")
    )
    return render(request, "exams/pending_assignments.html", {"assignments": assignments})


@login_required
def confirm_assignment(request, pk):
    """Approve a pending invigilation assignment."""
    assignment = get_object_or_404(InvigilationAssignment, pk=pk, status=InvigilationAssignment.PENDING_CONFIRMATION)
    assignment.status = InvigilationAssignment.CONFIRMED
    assignment.confirmed_at = timezone.now()
    assignment.save(update_fields=["status", "confirmed_at"])
    messages.success(request, f"Assignment for {assignment.faculty.user.get_full_name()} confirmed.")
    return redirect("exams:pending_assignments")


@login_required
def decline_assignment(request, pk):
    """Decline a pending invigilation assignment."""
    assignment = get_object_or_404(InvigilationAssignment, pk=pk, status=InvigilationAssignment.PENDING_CONFIRMATION)
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        assignment.status = InvigilationAssignment.DECLINED
        assignment.declined_at = timezone.now()
        assignment.save(update_fields=["status", "declined_at"])
        # Optionally store reason if you add a field later
        messages.success(request, f"Assignment for {assignment.faculty.user.get_full_name()} declined.")
        return redirect("exams:pending_assignments")
    return render(request, "exams/decline_assignment.html", {"assignment": assignment})
    """Export allocation details for a specific exam as CSV."""

    exam = get_object_or_404(Exam.objects.select_related("department"), pk=pk)
    assignments = (
        InvigilationAssignment.objects.filter(exam_session_hall__exam=exam)
        .select_related(
            "exam_session_hall__exam",
            "exam_session_hall__hall",
            "faculty__user",
            "faculty__department",
        )
        .order_by("exam_session_hall__hall__block", "exam_session_hall__hall__name")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename=exam_{exam.id}_allocation.csv"

    writer = csv.writer(response)
    writer.writerow([
        "exam_date",
        "start_time",
        "end_time",
        "course_code",
        "course_name",
        "hall",
        "block",
        "faculty_name",
        "faculty_department",
        "status",
    ])

    for a in assignments:
        ex = a.exam_session_hall.exam
        hall = a.exam_session_hall.hall
        fac = a.faculty
        user = fac.user
        writer.writerow([
            ex.exam_date,
            ex.start_time,
            ex.end_time,
            ex.course_code,
            ex.course_name,
            hall.name,
            hall.block,
            user.get_full_name() or user.username,
            fac.department.code if fac.department else "",
            a.status,
        ])

    return response


@login_required
def faculty_dashboard(request):
    """Dashboard for faculty to see and respond to invigilation assignments."""

    try:
        faculty = request.user.faculty_profile
    except Faculty.DoesNotExist:  # type: ignore[attr-defined]
        messages.error(request, "You do not have a faculty profile configured.")
        return redirect("accounts:dashboard")

    today = timezone.localdate()

    assignments = (
        InvigilationAssignment.objects.filter(faculty=faculty, exam_session_hall__exam__exam_date__gte=today)
        .select_related("exam_session_hall__exam", "exam_session_hall__hall")
        .order_by("exam_session_hall__exam__exam_date", "exam_session_hall__exam__start_time")
    )

    return render(request, "exams/faculty_dashboard.html", {"assignments": assignments})


@login_required
def confirm_assignment(request, pk):
    assignment = get_object_or_404(
        InvigilationAssignment.objects.select_related("faculty", "exam_session_hall__exam"), pk=pk
    )

    if not hasattr(request.user, "faculty_profile") or assignment.faculty != request.user.faculty_profile:  # type: ignore[attr-defined]
        messages.error(request, "You are not allowed to modify this assignment.")
        return redirect("exams:faculty_dashboard")

    assignment.status = InvigilationAssignment.CONFIRMED
    assignment.confirmed_at = timezone.now()
    assignment.save(update_fields=["status", "confirmed_at"])

    messages.success(request, "Your availability for this invigilation duty has been confirmed.")
    return redirect("exams:faculty_dashboard")


@login_required
def decline_assignment(request, pk):
    assignment = get_object_or_404(
        InvigilationAssignment.objects.select_related("faculty", "exam_session_hall__exam"), pk=pk
    )

    if not hasattr(request.user, "faculty_profile") or assignment.faculty != request.user.faculty_profile:  # type: ignore[attr-defined]
        messages.error(request, "You are not allowed to modify this assignment.")
        return redirect("exams:faculty_dashboard")

    assignment.status = InvigilationAssignment.DECLINED
    assignment.declined_at = timezone.now()
    assignment.save(update_fields=["status", "declined_at"])

    messages.success(request, "You have marked yourself as not available for this duty. Admin will be notified.")
    return redirect("exams:faculty_dashboard")

