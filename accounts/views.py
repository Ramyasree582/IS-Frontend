from datetime import timedelta
import secrets
import string

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q

from .forms import FacultyCreateForm
from .models import Faculty, LoginOTP
from exams.models import Department


class PlatformLoginView(LoginView):
    template_name = "accounts/login.html"

    def form_valid(self, form):
        """After successful authentication, enforce OTP + password change for faculty on first login."""
        response = super().form_valid(form)
        user = self.request.user

        # If the user is a faculty and must change password, redirect to OTP verification flow
        if hasattr(user, "faculty_profile") and user.faculty_profile.must_change_password:  # type: ignore[attr-defined]
            # Generate OTP
            code = f"{timezone.now().microsecond % 1000000:06d}"
            expires_at = timezone.now() + timedelta(minutes=10)
            LoginOTP.objects.create(user=user, code=code, expires_at=expires_at)

            # Send OTP via email
            send_mail(
                subject="Your first login OTP",
                message=f"Your OTP for first login is {code}. It is valid for 10 minutes.",
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True,
            )

            messages.info(self.request, "We have sent an OTP to your registered email. Please verify it to continue.")
            return redirect("accounts:verify_otp")

        return response


def public_home(request):
    """Public landing page visible without login."""

    return render(request, "home.html")


@login_required
def dashboard_router(request):
    """Send users to the correct dashboard based on their role.

    For now:
    - staff users (platform admins) -> exams admin dashboard
    - non-staff (faculty) -> faculty dashboard
    """

    if request.user.is_staff:
        return redirect("exams:admin_dashboard")

    return redirect("exams:faculty_dashboard")


@staff_member_required
def create_faculty(request):
    """Platform admin view to create a new faculty profile and send credentials by email."""

    User = get_user_model()

    if request.method == "POST":
        form = FacultyCreateForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            email = cd["email"].lower()

            # Generate a simple temporary password
            temp_password = User.objects.make_random_password()

            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=cd["first_name"],
                last_name=cd.get("last_name", ""),
                password=temp_password,
                is_staff=False,
            )

            faculty = Faculty.objects.create(
                user=user,
                employee_id=cd["employee_id"],
                department=cd["department"],
                cabin_block=cd.get("cabin_block", ""),
                cabin_room=cd.get("cabin_room", ""),
                phone_number=cd.get("phone_number", ""),
                must_change_password=True,
            )

            # Send email with username and temporary password
            send_mail(
                subject="Your Invigilation Platform Account",
                message=(
                    "Dear {name},\n\n"
                    "An account has been created for you on the Invigilation Management Platform.\n"
                    "Login details:\n"
                    "Username: {username}\n"
                    "Temporary password: {password}\n\n"
                    "On first login, you will be asked to verify an OTP and change your password.\n\n"
                    "Regards,\nAdmin"
                ).format(name=user.get_full_name() or user.username, username=user.username, password=temp_password),
                from_email=None,
                recipient_list=[email],
                fail_silently=True,
            )

            messages.success(request, "Faculty profile created and credentials sent by email.")
            return redirect("exams:admin_dashboard")
    else:
        form = FacultyCreateForm()

    return render(request, "accounts/faculty_create.html", {"form": form})


@login_required
def verify_otp(request):
    """Verify first-login OTP for faculty users."""

    user = request.user
    if not hasattr(user, "faculty_profile"):  # type: ignore[attr-defined]
        return redirect("accounts:dashboard")

    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        otp = (
            LoginOTP.objects.filter(user=user, code=code, is_used=False, expires_at__gte=timezone.now())
            .order_by("-created_at")
            .first()
        )
        if not otp:
            messages.error(request, "Invalid or expired OTP.")
        else:
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            # Mark that OTP is verified in the session and go to password change
            request.session["otp_verified"] = True
            messages.success(request, "OTP verified. Please set a new password.")
            return redirect("accounts:first_login_password_change")

    return render(request, "accounts/verify_otp.html")


@login_required
def first_login_password_change(request):
    """Force faculty to change password after OTP verification on first login."""

    user = request.user
    if not hasattr(user, "faculty_profile"):  # type: ignore[attr-defined]
        return redirect("accounts:dashboard")

    if not request.session.get("otp_verified"):
        return redirect("accounts:verify_otp")

    if request.method == "POST":
        form = PasswordChangeForm(user=user, data=request.POST)
        if form.is_valid():
            form.save()
            # Clear flag so future logins go directly to dashboard
            user.faculty_profile.must_change_password = False  # type: ignore[attr-defined]
            user.faculty_profile.save(update_fields=["must_change_password"])
            request.session.pop("otp_verified", None)
            messages.success(request, "Password changed successfully.")
            return redirect("accounts:dashboard")
    else:
        form = PasswordChangeForm(user=user)

    return render(request, "accounts/first_login_password_change.html", {"form": form})


@staff_member_required
def faculty_list(request):
    """List all faculty with search and pagination."""
    faculty_qs = Faculty.objects.select_related("user", "department").order_by("user__last_name", "user__first_name")
    q = request.GET.get("q", "").strip()
    if q:
        faculty_qs = faculty_qs.filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(employee_id__icontains=q) | Q(user__email__icontains=q)
        )
    return render(request, "accounts/faculty_list.html", {"faculty": faculty_qs, "q": q})


def _generate_random_password(length=12):
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@staff_member_required
def create_faculty_batch(request):
    """Batch faculty creation page with dynamic rows."""
    departments = Department.objects.all().order_by("code")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_row":
            # Return a new empty row as HTML for AJAX insertion
            row_index = int(request.POST.get("row_index", 0))
            context = {"departments": departments, "row_index": row_index}
            return render(request, "accounts/partials/faculty_batch_row.html", context)
        elif action == "create":
            # Process bulk creation
            employee_ids = request.POST.getlist("employee_id")
            first_names = request.POST.getlist("first_name")
            last_names = request.POST.getlist("last_name")
            emails = request.POST.getlist("email")
            department_ids = request.POST.getlist("department")
            cabin_blocks = request.POST.getlist("cabin_block")
            cabin_rooms = request.POST.getlist("cabin_room")
            phones = request.POST.getlist("phone_number")

            created_count = 0
            skipped = []
            for i, emp_id in enumerate(employee_ids):
                if not emp_id.strip():
                    continue
                if Faculty.objects.filter(employee_id=emp_id.strip()).exists():
                    skipped.append(emp_id.strip())
                    continue
                if get_user_model().objects.filter(email=emails[i].strip()).exists():
                    skipped.append(emails[i].strip())
                    continue
                department = Department.objects.get(id=department_ids[i])
                # Generate username and random password
                username = f"{first_names[i].strip().lower()}.{last_names[i].strip().lower()}"
                password = _generate_random_password()
                user = get_user_model().objects.create_user(username=username, email=emails[i].strip(), password=password, is_staff=False)
                user.first_name = first_names[i].strip()
                user.last_name = last_names[i].strip()
                user.save()
                faculty = Faculty.objects.create(
                    user=user,
                    employee_id=emp_id.strip(),
                    department=department,
                    cabin_block=cabin_blocks[i].strip(),
                    cabin_room=cabin_rooms[i].strip(),
                    phone_number=phones[i].strip(),
                    must_change_password=True,
                )
                # Send credentials via email
                subject = "Your Faculty Account Credentials"
                message = (
                    f"Dear {user.get_full_name()},\n\n"
                    f"Your faculty account has been created.\n\n"
                    f"Username: {username}\n"
                    f"Password: {password}\n\n"
                    f"Login URL: {request.scheme}://{request.get_host()}/accounts/login/\n\n"
                    f"On first login, you will be prompted to verify an OTP sent to this email and then change your password.\n"
                    f"If you face any issues, contact the admin."
                )
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                created_count += 1
            if skipped:
                messages.warning(request, f"Skipped {len(skipped)} duplicates: {', '.join(skipped)}")
            messages.success(request, f"Created {created_count} faculty profiles. Credentials have been emailed to each faculty.")
            return redirect("accounts:faculty_list")
    return render(request, "accounts/create_faculty_batch.html", {"departments": departments})


def forgot_password(request):
    """Send OTP to faculty email for password reset."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        try:
            user = get_user_model().objects.get(email__iexact=email)
            faculty = user.faculty_profile
        except (get_user_model().DoesNotExist, AttributeError):
            messages.error(request, "No faculty account found with this email.")
            return render(request, "accounts/forgot_password.html", {"email": email})

        # Generate OTP
        code = f"{timezone.now().microsecond % 1000000:06d}"
        expires_at = timezone.now() + timedelta(minutes=10)
        LoginOTP.objects.filter(user=user).delete()
        LoginOTP.objects.create(user=user, code=code, expires_at=expires_at)

        send_mail(
            subject="Password Reset OTP",
            message=f"Your OTP to reset password is {code}. It is valid for 10 minutes.",
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )
        messages.success(request, "An OTP has been sent to your email. Please use it to reset your password.")
        return redirect("accounts:reset_password_with_otp")

    return render(request, "accounts/forgot_password.html")


def reset_password_with_otp(request):
    """Reset password after OTP verification."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        code = request.POST.get("code", "").strip()
        new_password = request.POST.get("new_password", "").strip()
        if not (email and code and new_password):
            messages.error(request, "All fields are required.")
            return render(request, "accounts/reset_password_with_otp.html", {"email": email})

        try:
            user = get_user_model().objects.get(email__iexact=email)
            otp = LoginOTP.objects.filter(user=user, code=code, is_used=False, expires_at__gte=timezone.now()).first()
            if not otp:
                messages.error(request, "Invalid or expired OTP.")
                return render(request, "accounts/reset_password_with_otp.html", {"email": email})
            # Mark OTP as used
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            # Set new password
            user.set_password(new_password)
            user.save()
            # Reset must_change_password flag so they aren’t forced into OTP flow again
            if hasattr(user, "faculty_profile"):
                user.faculty_profile.must_change_password = False
                user.faculty_profile.save(update_fields=["must_change_password"])
            messages.success(request, "Your password has been reset. You can now log in.")
            return redirect("accounts:login")
        except get_user_model().DoesNotExist:
            messages.error(request, "Invalid email.")
            return render(request, "accounts/reset_password_with_otp.html", {"email": email})

    return render(request, "accounts/reset_password_with_otp.html")

