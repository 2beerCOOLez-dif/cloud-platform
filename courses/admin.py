from django.contrib import admin

from .models import Assignment, Course, Enrollment, Lesson, Submission


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "teacher",
        "is_published",
        "created_at",
    )
    list_filter = ("is_published",)
    search_fields = (
        "title",
        "description",
        "teacher__username",
    )


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order")
    list_filter = ("course",)
    search_fields = ("title", "content")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "enrolled_at")
    list_filter = ("course",)
    search_fields = (
        "student__username",
        "course__title",
    )


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "lesson", "created_at")
    search_fields = ("title", "description")
    list_select_related = ("lesson",)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "assignment",
        "grade",
        "submitted_at",
    )
    search_fields = (
        "student__username",
        "assignment__title",
    )
    list_select_related = ("student", "assignment")
    readonly_fields = ("submitted_at", "reviewed_at")