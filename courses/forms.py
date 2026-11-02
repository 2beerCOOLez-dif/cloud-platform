from django import forms

from .models import Assignment, Course, Lesson, Submission


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["title", "description", "is_published"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
        }

class LessonForm(forms.ModelForm):
    order = forms.IntegerField(
        label="Порядок",
        min_value=1,
    )

    class Meta:
        model = Lesson
        fields = ["title", "video_url", "content", "order"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 12}),
        }

class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["title", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 8}),
        }

class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ["answer"]
        widgets = {
            "answer": forms.Textarea(attrs={"rows": 10}),
        }


class GradeForm(forms.ModelForm):
    grade = forms.IntegerField(
        label="Оценка от 0 до 100",
        min_value=0,
        max_value=100,
    )

    class Meta:
        model = Submission
        fields = ["grade", "teacher_comment"]
        widgets = {
            "teacher_comment": forms.Textarea(attrs={"rows": 5}),
        }