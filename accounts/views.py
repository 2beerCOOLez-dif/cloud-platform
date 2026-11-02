from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from courses.models import Course


@login_required
def dashboard(request):
    user = request.user

    if user.is_superuser:
        courses = Course.objects.select_related("teacher")
        section_title = "Все курсы платформы"
    elif user.role == "teacher":
        courses = (
            Course.objects
            .filter(teacher=user)
            .select_related("teacher")
        )
        section_title = "Мои преподавательские курсы"
    else:
        courses = (
            Course.objects
            .filter(
                enrollments__student=user,
                is_published=True,
            )
            .select_related("teacher")
        )
        section_title = "Мои курсы"

    return render(
        request,
        "accounts/dashboard.html",
        {
            "courses": courses,
            "section_title": section_title,
        },
    )