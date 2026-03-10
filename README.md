## Faculty Invigilation Management System

### 1. Project Overview

This project is a **Faculty Invigilation Management System** for colleges and universities. It streamlines:

- **Admins**: create faculty profiles, manage departments and halls, upload exam timetables, auto‑allocate invigilation duties, and approve/decline leaves.
- **Faculty**: securely log in, view and respond to invigilation duties, manage their weekly teaching timetable, and apply for leave.

The system is built as a classic Django monolith with **server‑rendered templates** styled using **Tailwind CSS** for a clean and responsive UI.

---

### 2. Tech Stack

- **Language**: Python
- **Web framework**: Django 5.x
- **Database (default)**: SQLite (`db.sqlite3`)
- **Templating**: Django templates in the `templates/` directory
- **Styling**: Tailwind CSS (via CDN) + small custom configuration in `base.html`
- **Email**: SMTP (e.g. Gmail) configured in `invigilation_system/settings.py`

#### Django apps

- `accounts`: user authentication, faculty profiles, OTP flows, first‑login password change, forgot/reset password, admin tools to create faculty.
- `exams`: departments, exam halls, exam sessions, invigilation assignments, CSV upload for exam timetable, auto‑allocation logic, admin dashboards, faculty dashboard.
- `timetable`: courses and weekly teaching slots for faculty; CSV upload for timetables; faculty timetable grid and slot management.
- `leaves`: faculty leave requests and admin approval workflow.

---

### 3. Backend Design

#### 3.1 Key models (simplified)

- `accounts.Faculty`
  - One‑to‑one with Django’s `User`.
  - Fields: `employee_id`, `department`, `cabin_block`, `cabin_room`, `phone_number`, `is_active`, `must_change_password`.

- `accounts.LoginOTP`
  - Stores OTP codes for first login and password reset.
  - Fields: `user`, `code`, `created_at`, `expires_at`, `is_used`.

- `exams.Department`
  - Department code and name (e.g. `ECE`, `CSE`).

- `exams.ExamHall`
  - Represents a physical hall/room with block, floor, and capacity.

- `exams.Exam`
  - One exam slot: course code/name, type (`MID`, `END`, `TEST`), department, year, semester, date, start/end time.

- `exams.ExamSessionHall`
  - Connects an `Exam` to a specific `ExamHall` with `required_invigilators`.

- `exams.InvigilationAssignment`
  - Connects a `Faculty` to a specific `ExamSessionHall` with a `status`:
    - `PENDING_CONFIRMATION`, `CONFIRMED`, `DECLINED`, `CANCELLED`, `REASSIGNED`.

- `timetable.Course`
  - A subject with `year`, `code`, `name`.

- `timetable.FacultyTimeSlot`
  - A repeated weekly teaching slot for a faculty member:
    - `day_of_week`, `start_time`, `end_time`, `course_code`, `course_name`, `year`, `is_lab`.

- `leaves.FacultyLeave`
  - Stores leave requests: `start_date`, `end_date`, `reason`, and `status` (`PENDING`, `APPROVED`, `REJECTED`).

#### 3.2 Core flows

- **Authentication & roles**
  - Admins and faculty both use Django’s `User` model.
  - Admins (`is_staff=True`) see the admin dashboards.
  - Faculty have a linked `Faculty` profile and see the faculty dashboard.

- **OTP + first login**
  - For newly created faculty, `must_change_password=True`.
  - On first login with the temporary password:
    - An OTP is generated and emailed (`LoginOTP`).
    - User is redirected to `/accounts/verify-otp/`.
    - After a valid OTP, they must set a new password on `/accounts/first-login-password/`.
    - `must_change_password` is then set to `False`.

- **Forgot password**
  - Faculty can request a password reset OTP by email and then set a new password via `/accounts/reset-password-with-otp/`.

---

### 4. Algorithms and Business Logic

#### 4.1 Invigilation auto‑allocation

In `exams/views.py` (`auto_allocate_for_exam`), the system auto‑assigns invigilation duties:

1. **Inputs**
   - A specific `Exam`.
   - Configured `ExamSessionHall` entries for that exam (rooms + required invigilators).

2. **Eligibility filters**
   - Start from all active faculty (`Faculty.is_active=True`).
   - Exclude faculty from the **same department** as the exam.
   - Exclude faculty already assigned to any hall for this exam.
   - Exclude faculty who are **on approved leave** on the exam date (`FacultyLeave`).
   - Exclude faculty with a **timetable clash**:
     - For each `FacultyTimeSlot` on the exam’s weekday, if the time intervals overlap, that faculty is considered unavailable.
     - Exception: if the slot’s `year` matches the exam’s `year`, the system assumes that class is cancelled for exams of that year, so the slot does **not** block invigilation.

3. **Scoring & fairness**
   - Each eligible faculty gets a `score`:
     - +10 points if their cabin block matches the exam hall’s block (proximity bonus).
   - The system also counts current invigilation load (`InvigilationAssignment` count per faculty).
   - Faculty are sorted by:
     - Higher `score` first.
     - Lower current load second (fair distribution).

4. **Assignment**
   - For each `ExamSessionHall`, choose up to `required_invigilators` from the sorted eligible list.
   - Create `InvigilationAssignment` entries with:
     - Status `PENDING_CONFIRMATION`.
     - A confirmation deadline (1.5 hours before exam start).

The result is a **proximity‑aware, balanced** duty assignment that respects teaching slots and approved leave.

#### 4.2 Faculty timetable clash detection

Helper `_faculty_has_clash(faculty, exam)`:

- Builds datetime intervals for the exam and for each of the faculty’s weekly teaching slots on that weekday.
- Treats overlapping intervals as clashes, except when the teaching slot’s `year` equals `exam.year` (class likely cancelled due to exam).

#### 4.3 Leave impact on allocation

Helper `_faculty_on_approved_leave(faculty, exam_date)`:

- Checks if the exam date falls within any approved `FacultyLeave` interval.
- Such faculty are excluded from auto‑allocation for that exam.

---

### 5. Frontend UI (Tailwind‑based)

All templates extend `templates/base.html`, which:

- Includes Tailwind via CDN with a custom theme (fonts, primary color).
- Provides a top navigation bar that adapts to the user:
  - Admin dashboard links for staff.
  - Faculty dashboard, timetable, and leaves links for faculty.
  - Login/Logout buttons.
- Renders Django `messages` using colored Tailwind alert styles.
- Wraps content in a centered, responsive container and includes a footer.

#### 5.1 Public and auth pages

- **Home** (`templates/home.html`, `/`):
  - Hero section describing the invigilation system.
  - Buttons to go to admin or faculty dashboard if logged in.
  - “Login to Continue” button for anonymous users.

- **Login** (`templates/accounts/login.html`, `/accounts/login/`):
  - Centered card with username/password.
  - Link to “Forgot password?”.

- **Verify OTP** (`templates/accounts/verify_otp.html`, `/accounts/verify-otp/`):
  - Input for 6‑digit OTP with validity notice.

- **First login password change** (`templates/accounts/first_login_password_change.html`, `/accounts/first-login-password/`):
  - Form to set a new password after OTP verification.

- **Forgot password / Reset with OTP**:
  - `/accounts/forgot-password/`: enter email to receive OTP.
  - `/accounts/reset-password-with-otp/`: email + OTP + new password form.

#### 5.2 Admin UI (`exams` + `accounts` + `timetable` + `leaves`)

- **Admin dashboard** (`/exams/admin/`):
  - Tailwind cards summarizing:
    - Upcoming exams.
    - Exams today.
    - Pending confirmations.
    - Total faculty.
  - Quick action buttons:
    - Upload exam timetable (CSV).
    - Manage exams, departments, halls, blocks.
    - Manage courses/subjects.
    - Batch create faculty.
    - Approve/decline duties and leaves.
  - Table of upcoming exams with “View” and “Assign Duties” actions.

- **Exams management**:
  - `/exams/admin/exams/`: list of exams with date/time/course/department and actions.
  - `/exams/admin/exams/<pk>/`: exam detail with:
    - Exam meta (course, date, time, department).
    - Buttons to:
      - Auto‑allocate invigilators.
      - Configure halls/rooms for the exam.
      - Export allocation to CSV.
    - Table of halls vs. assigned invigilators, with status badges.

- **Halls and blocks**:
  - `/exams/admin/halls/`: add/delete halls with block, room, floor, capacity.
  - `/exams/admin/blocks/`: overview of blocks.
  - `/exams/admin/blocks/<block>/`: rooms in a block, plus cabin info for faculty with cabins in those rooms.

- **Exams timetable upload**:
  - `/exams/admin/upload-timetable/`:
    - Upload a CSV with columns:
      - `department_code`, `course_code`, `course_name`, `exam_type`, `year`, `semester`, `exam_date`, `start_time`, `end_time`.
    - Example file: `exam_timetable_ece3.csv` provided in the repo.

- **Pending assignments and allocation overview**:
  - `/exams/admin/pending-assignments/`: list pending invigilation assignments to approve/decline.
  - `/exams/admin/allocation-overview/`: filterable table (by date and block) showing all active assignments.

- **Faculty management** (`accounts`):
  - `/accounts/faculty/create/`: responsive form to create a single faculty profile.
  - `/accounts/faculty/create-batch/`: batch creation using a dynamic table; each row is one faculty member.
  - `/accounts/faculty/list/`: searchable list of all faculty with status badges and cabin info.

- **Timetable management** (`timetable`):
  - `/timetable/admin/upload/`: upload faculty timetable via CSV:
    - Columns: `employee_id, day, start_time, end_time, course_code, course_name, is_lab`.
  - `/timetable/admin/courses/`: manage courses/subjects by year.

- **Leave management** (`leaves`):
  - `/leaves/admin/`: admin view of all leave requests with approve/reject actions.

#### 5.3 Faculty UI

- **Faculty dashboard** (`/exams/faculty/dashboard/`):
  - Table of upcoming invigilation duties with:
    - Date, time, course, hall, block, status.
  - If a duty is pending, faculty can:
    - Confirm availability.
    - Mark themselves as not available (admin will reassign).

- **Timetable** (`/timetable/faculty/`):
  - Responsive grid with days vs. fixed time slots.
  - Each cell shows one or more teaching slots with course info, year, and lab badge.
  - Delete buttons for removing a slot.
  - “Add Time Slot” goes to `/timetable/faculty/add/`.

- **Leaves**:
  - `/leaves/faculty/` (`leaves:my_leaves`): list of all leave requests with colored status badges.
  - `/leaves/faculty/apply/`: Tailwind form to submit a new leave request.

---

### 6. Running the Project Locally (Step by Step)

#### 6.1 Setup (once)

1. **Clone and open the project**

   ```powershell
   cd "C:\Users\DELL\OneDrive\Desktop\New Project"
   # repo is already cloned into IS-BackEnd/
   ```

2. **Create and activate virtualenv (PowerShell)**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**

   Ideally:

   ```powershell
   pip install -r IS-BackEnd\requirements.txt
   ```

   If `psycopg2-binary` fails due to missing `pg_config`, you can install at least Django:

   ```powershell
   pip install Django==5.0.4
   ```

4. **Apply database migrations**

   ```powershell
   cd IS-BackEnd
   python manage.py migrate
   ```

5. **Create an admin (superuser)**

   ```powershell
   python manage.py createsuperuser
   ```

   - Choose a username, email, and password.

6. **Run the server**

   ```powershell
   python manage.py runserver
   ```

7. **Open the app**

   - Home: `http://127.0.0.1:8000/`
   - Admin login: `http://127.0.0.1:8000/accounts/login/`

---

### 7. Typical Usage Flow

#### 7.1 Admin workflow

1. **Login as admin**
   - Go to `/accounts/login/`, use the superuser credentials.

2. **Ensure departments and halls exist**
   - Departments: `/exams/admin/departments/`
   - Halls (rooms): `/exams/admin/halls/`

3. **Upload exam timetable**
   - Go to `/exams/admin/upload-timetable/`.
   - Select `exam_timetable_ece3.csv`.
   - After upload, verify exams at `/exams/admin/exams/`.

4. **Create faculty profiles**
   - Single: `/accounts/faculty/create/`.
   - Batch: `/accounts/faculty/create-batch/`.
   - Each faculty receives an email with username and temporary password.

5. **Upload faculty timetable (optional but recommended)**
   - `/timetable/admin/upload/`: upload faculty teaching slots via CSV.

6. **Configure exam rooms and auto‑allocate duties**
   - From `/exams/admin/exams/`, open an exam detail page.
   - Use “Assign duties (select rooms)” to choose halls and required invigilators.
   - Click “Auto‑allocate invigilators” to run the allocation algorithm.

7. **Monitor and manage allocations and leaves**
   - `/exams/admin/allocation-overview/`: overview of active allocations.
   - `/exams/admin/pending-assignments/`: approve/decline duties.
   - `/leaves/admin/`: approve/decline leave requests.

#### 7.2 Faculty workflow

1. **Receive credentials**
   - Admin creates a profile; system emails username + temporary password + login URL.

2. **First login**
   - Visit `/accounts/login/`, enter username + temporary password.
   - System sends an OTP and routes to `/accounts/verify-otp/`.
   - Enter OTP to continue to `/accounts/first-login-password/`.
   - Set a new password.

3. **Use the system**
   - **Dashboard**: `/exams/faculty/dashboard/` – see upcoming duties, confirm/decline.
   - **Timetable**: `/timetable/faculty/` – view teaching slots; `/timetable/faculty/add/` to add a slot.
   - **Leaves**: `/leaves/faculty/` – view requests; `/leaves/faculty/apply/` to request leave.

4. **Forgot password**
   - `/accounts/forgot-password/`: request a reset OTP.
   - `/accounts/reset-password-with-otp/`: set a new password using email + OTP.

---

### 8. Notes and Customization

- **Email settings** in `invigilation_system/settings.py` are configured for Gmail SMTP. You should:
  - Replace `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` with your own.
  - Use an app password if required by your email provider.

- **Database backend** is SQLite by default for easy local setup. For production, you can switch `DATABASES['default']['ENGINE']` to PostgreSQL and install `psycopg2-binary` with proper `pg_config` available.

- **Tailwind** is loaded via CDN for simplicity. For larger projects or production, consider integrating a proper Tailwind build pipeline.

This README should give you a complete, end‑to‑end understanding of how the project is structured, how the algorithms work, and how to run and use the system as both admin and faculty.

---

### 9. Email setup (OTP & faculty credentials)

Email is used to send:

- **New faculty credentials** (username + temporary password).
- **First‑login OTP codes**.
- **Forgot‑password OTP codes**.

By default, the project is configured to **print emails to the terminal only** so you can test flows without any SMTP account.

```python
# invigilation_system/settings.py
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in {"1", "true", "yes"}
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@invigilation.local")
```

- With this default, any email sent by the app will appear in the **Django runserver console**, not in a real inbox.

#### 9.1 Use real SMTP (recommended for actual usage)

To deliver emails to real faculty mailboxes, switch to an SMTP backend via **environment variables** before running the server.

Example for **Gmail with an app password** (PowerShell on Windows, from the `IS-BackEnd` folder):

```powershell
# 1) Activate virtualenv (if not already)
cd "C:\Users\abhin\OneDrive\Desktop\Project"
.\.venv\Scripts\Activate.ps1
cd IS-BackEnd

# 2) Configure email environment variables
$env:EMAIL_BACKEND       = "django.core.mail.backends.smtp.EmailBackend"
$env:EMAIL_HOST          = "smtp.gmail.com"
$env:EMAIL_PORT          = "587"
$env:EMAIL_USE_TLS       = "True"
$env:EMAIL_HOST_USER     = "your_gmail_address@gmail.com"
$env:EMAIL_HOST_PASSWORD = "your_app_password"   # NOT your normal password
$env:DEFAULT_FROM_EMAIL  = $env:EMAIL_HOST_USER

# 3) Start Django in the same PowerShell session
python manage.py runserver
```

Notes:

- Use a **Gmail app password**, not your main Google password (Google Account → Security → App passwords).
- Keep these values secret; do **not** commit them to git.
- For a different provider (college SMTP, Outlook, etc.) change `EMAIL_HOST`, `EMAIL_PORT`, and `EMAIL_USE_TLS` to match their documentation.

Once configured, flows like:

- Creating faculty (`/accounts/faculty/create/`, `/accounts/faculty/create-batch/`).
- First login (OTP).
- Forgot password.

will send emails to the addresses configured for each faculty user.

