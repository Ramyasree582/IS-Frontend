from django import forms
from django.contrib.auth.models import User

from exams.models import Department
from .models import Faculty


class FacultyCreateForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()
    employee_id = forms.CharField(max_length=20)
    department = forms.ModelChoiceField(queryset=Department.objects.all())
    cabin_block = forms.CharField(max_length=50, required=False)
    cabin_room = forms.CharField(max_length=50, required=False)
    phone_number = forms.CharField(max_length=20, required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_employee_id(self):
        employee_id = self.cleaned_data["employee_id"]
        if Faculty.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError("A faculty with this employee ID already exists.")
        return employee_id
