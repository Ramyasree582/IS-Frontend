from django import forms


class ExamTimetableUploadForm(forms.Form):
    file = forms.FileField(
        help_text=(
            "CSV columns: department_code, course_code, course_name, exam_type, "
            "year, semester, exam_date (YYYY-MM-DD), start_time (HH:MM), end_time (HH:MM)"
        )
    )
