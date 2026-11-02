from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from .forms import (
    AssignmentForm,
    CourseForm,
    GradeForm,
    LessonForm,
    SubmissionForm,
)
from .models import Assignment, Course, Enrollment, Lesson, Submission
from django.utils import timezone
from .video import get_video_data


def _can_view_lessons(user, course):
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    if user.role == "teacher":
        return course.teacher_id == user.pk

    if user.role == "student":
        return Enrollment.objects.filter(
            student=user,
            course=course,
        ).exists()

    return False


def course_list(request):
    query = request.GET.get("q", "").strip()

    courses = (
        Course.objects
        .filter(is_published=True)
        .select_related("teacher")
        .annotate(lesson_count=Count("lessons"))
    )

    if query:
        courses = courses.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
        )

    return render(
        request,
        "courses/course_list.html",
        {"courses": courses, "query": query},
    )


def course_detail(request, pk):
    course = get_object_or_404(
        Course.objects.select_related("teacher"),
        pk=pk,
        is_published=True,
    )

    can_view_lessons = _can_view_lessons(request.user, course)

    can_enroll = (
        request.user.is_authenticated
        and not request.user.is_superuser
        and request.user.role == "student"
        and not can_view_lessons
    )

    return render(
        request,
        "courses/course_detail.html",
        {
            "course": course,
            "can_view_lessons": can_view_lessons,
            "can_enroll": can_enroll,
        },
    )


@login_required
@require_POST
def enroll_course(request, pk):
    if request.user.is_superuser or request.user.role != "student":
        raise PermissionDenied("Записываться на курсы могут студенты.")

    course = get_object_or_404(
        Course,
        pk=pk,
        is_published=True,
    )

    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        course=course,
    )

    if created:
        messages.success(request, "Вы успешно записались на курс.")
    else:
        messages.info(request, "Вы уже записаны на этот курс.")

    return redirect("courses:course_detail", pk=course.pk)


@login_required
def lesson_detail(request, pk):
    lesson = get_object_or_404(
        Lesson.objects.select_related("course"),
        pk=pk,
        course__is_published=True,
    )

    if not _can_view_lessons(request.user, lesson.course):
        raise PermissionDenied("У вас нет доступа к материалам этого курса.")

    return render(
        request,
        "courses/lesson_detail.html",
        {
            "lesson": lesson,
            "video": get_video_data(lesson.video_url),
        },
    )

def _require_teacher(user):
    if user.role != "teacher":
        raise PermissionDenied("Управление курсами доступно преподавателям.")


def _get_teacher_course(user, pk):
    _require_teacher(user)

    return get_object_or_404(
        Course,
        pk=pk,
        teacher=user,
    )


@login_required
@require_http_methods(["GET", "POST"])
def course_create(request):
    _require_teacher(request.user)

    if request.method == "POST":
        form = CourseForm(request.POST)

        if form.is_valid():
            course = form.save(commit=False)
            course.teacher = request.user
            course.save()

            messages.success(request, "Курс создан.")
            return redirect("accounts:dashboard")
    else:
        form = CourseForm()

    return render(
        request,
        "courses/course_form.html",
        {
            "form": form,
            "page_title": "Создание курса",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def course_edit(request, pk):
    course = _get_teacher_course(request.user, pk)

    if request.method == "POST":
        form = CourseForm(request.POST, instance=course)

        if form.is_valid():
            form.save()

            messages.success(request, "Изменения сохранены.")
            return redirect("accounts:dashboard")
    else:
        form = CourseForm(instance=course)

    return render(
        request,
        "courses/course_form.html",
        {
            "form": form,
            "page_title": "Редактирование курса",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def course_delete(request, pk):
    course = _get_teacher_course(request.user, pk)

    if request.method == "POST":
        course.delete()

        messages.success(request, "Курс удалён.")
        return redirect("accounts:dashboard")

    return render(
        request,
        "courses/course_confirm_delete.html",
        {"course": course},
    )


def _get_teacher_lesson(user, pk):
    _require_teacher(user)

    return get_object_or_404(
        Lesson.objects.select_related("course"),
        pk=pk,
        course__teacher=user,
    )


@login_required
@require_http_methods(["GET", "HEAD"])
def course_manage(request, pk):
    course = _get_teacher_course(request.user, pk)

    return render(
        request,
        "courses/course_manage.html",
        {
            "course": course,
            "lessons": course.lessons.prefetch_related("assignments"),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def lesson_create(request, course_pk):
    course = _get_teacher_course(request.user, course_pk)

    if request.method == "POST":
        form = LessonForm(request.POST)

        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()

            messages.success(request, "Урок добавлен.")
            return redirect("courses:course_manage", pk=course.pk)
    else:
        max_order = (
            course.lessons.aggregate(value=Max("order"))["value"]
            or 0
        )
        form = LessonForm(initial={"order": max_order + 1})

    return render(
        request,
        "courses/lesson_form.html",
        {
            "form": form,
            "course": course,
            "page_title": "Добавление урока",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def lesson_edit(request, pk):
    lesson = _get_teacher_lesson(request.user, pk)

    if request.method == "POST":
        form = LessonForm(request.POST, instance=lesson)

        if form.is_valid():
            form.save()

            messages.success(request, "Урок обновлён.")
            return redirect(
                "courses:course_manage",
                pk=lesson.course_id,
            )
    else:
        form = LessonForm(instance=lesson)

    return render(
        request,
        "courses/lesson_form.html",
        {
            "form": form,
            "course": lesson.course,
            "page_title": "Редактирование урока",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def lesson_delete(request, pk):
    lesson = _get_teacher_lesson(request.user, pk)
    course = lesson.course

    if request.method == "POST":
        lesson.delete()

        messages.success(request, "Урок удалён.")
        return redirect("courses:course_manage", pk=course.pk)

    return render(
        request,
        "courses/lesson_confirm_delete.html",
        {
            "lesson": lesson,
            "course": course,
        },
    )

def _get_teacher_assignment(user, pk):
    _require_teacher(user)

    return get_object_or_404(
        Assignment.objects.select_related("lesson__course"),
        pk=pk,
        lesson__course__teacher=user,
    )


@login_required
@require_http_methods(["GET", "POST"])
def assignment_create(request, lesson_pk):
    lesson = _get_teacher_lesson(request.user, lesson_pk)

    if request.method == "POST":
        form = AssignmentForm(request.POST)

        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.lesson = lesson
            assignment.save()

            messages.success(request, "Задание добавлено.")
            return redirect(
                "courses:course_manage",
                pk=lesson.course_id,
            )
    else:
        form = AssignmentForm()

    return render(
        request,
        "courses/assignment_form.html",
        {
            "form": form,
            "lesson": lesson,
            "page_title": "Добавление задания",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def assignment_edit(request, pk):
    assignment = _get_teacher_assignment(request.user, pk)

    if request.method == "POST":
        form = AssignmentForm(request.POST, instance=assignment)

        if form.is_valid():
            form.save()

            messages.success(request, "Задание обновлено.")
            return redirect(
                "courses:course_manage",
                pk=assignment.lesson.course_id,
            )
    else:
        form = AssignmentForm(instance=assignment)

    return render(
        request,
        "courses/assignment_form.html",
        {
            "form": form,
            "lesson": assignment.lesson,
            "page_title": "Редактирование задания",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def assignment_delete(request, pk):
    assignment = _get_teacher_assignment(request.user, pk)
    course_pk = assignment.lesson.course_id

    if request.method == "POST":
        assignment.delete()

        messages.success(request, "Задание удалено.")
        return redirect("courses:course_manage", pk=course_pk)

    return render(
        request,
        "courses/assignment_confirm_delete.html",
        {"assignment": assignment},
    )


@login_required
@require_http_methods(["GET", "POST"])
def assignment_answer(request, pk):
    if request.user.is_superuser or request.user.role != "student":
        raise PermissionDenied("Отправлять ответы могут студенты.")

    assignment = get_object_or_404(
        Assignment.objects.select_related("lesson__course"),
        pk=pk,
        lesson__course__is_published=True,
    )

    if not _can_view_lessons(request.user, assignment.lesson.course):
        raise PermissionDenied("Сначала запишитесь на курс.")

    submission = Submission.objects.filter(
        assignment=assignment,
        student=request.user,
    ).first()

    form = SubmissionForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST":
        if submission is not None:
            messages.info(request, "Ваш ответ уже отправлен.")
            return redirect("courses:assignment_answer", pk=assignment.pk)

        if form.is_valid():
            submission, created = Submission.objects.get_or_create(
                assignment=assignment,
                student=request.user,
                defaults={"answer": form.cleaned_data["answer"]},
            )

            if created:
                messages.success(request, "Ответ отправлен преподавателю.")
            else:
                messages.info(request, "Ваш ответ уже отправлен.")

            return redirect("courses:assignment_answer", pk=assignment.pk)

    return render(
        request,
        "courses/assignment_answer.html",
        {
            "assignment": assignment,
            "submission": submission,
            "form": form,
        },
    )


@login_required
@require_http_methods(["GET", "HEAD"])
def assignment_submissions(request, pk):
    assignment = _get_teacher_assignment(request.user, pk)

    submissions = assignment.submissions.select_related("student")

    return render(
        request,
        "courses/assignment_submissions.html",
        {
            "assignment": assignment,
            "submissions": submissions,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def submission_review(request, pk):
    _require_teacher(request.user)

    submission = get_object_or_404(
        Submission.objects.select_related(
            "student",
            "assignment__lesson__course",
        ),
        pk=pk,
        assignment__lesson__course__teacher=request.user,
    )

    form = GradeForm(
        request.POST if request.method == "POST" else None,
        instance=submission,
    )

    if request.method == "POST" and form.is_valid():
        reviewed_submission = form.save(commit=False)
        reviewed_submission.reviewed_at = timezone.now()
        reviewed_submission.save()

        messages.success(request, "Оценка и комментарий сохранены.")
        return redirect(
            "courses:assignment_submissions",
            pk=submission.assignment_id,
        )

    return render(
        request,
        "courses/submission_review.html",
        {
            "submission": submission,
            "form": form,
        },
    )