from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from .validators import validate_video_url

class Course(models.Model):
    title = models.CharField(
        "Название",
        max_length=200,
    )
    description = models.TextField("Описание")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="teaching_courses",
        limit_choices_to={"role": "teacher"},
        verbose_name="Преподаватель",
    )
    is_published = models.BooleanField(
        "Опубликован",
        default=False,
    )
    created_at = models.DateTimeField(
        "Дата создания",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Lesson(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="lessons",
        verbose_name="Курс",
    )
    title = models.CharField(
        "Название",
        max_length=200,
    )
    content = models.TextField("Содержание")
    order = models.PositiveIntegerField(
        "Порядок",
        default=1,
    )
    video_url = models.URLField(
        "Ссылка на вебинар",
        max_length=500,
        blank=True,
        default="",
        validators=[validate_video_url],
        help_text=(
            "Ссылка на видео YouTube, Rutube или Vimeo. "
            "Можно оставить пустым."
        ),
    )

    class Meta:
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.course.title}: {self.title}"


class Enrollment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
        limit_choices_to={"role": "student"},
        verbose_name="Студент",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="Курс",
    )
    enrolled_at = models.DateTimeField(
        "Дата записи",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Запись на курс"
        verbose_name_plural = "Записи на курсы"
        ordering = ["-enrolled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"],
                name="unique_student_course",
            ),
        ]

    def __str__(self):
        return f"{self.student.username} — {self.course.title}"


class Assignment(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="Урок",
    )
    title = models.CharField(
        "Название",
        max_length=200,
    )
    description = models.TextField("Условие задания")
    created_at = models.DateTimeField(
        "Дата создания",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Задание"
        verbose_name_plural = "Задания"
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.title


class Submission(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Задание",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissions",
        limit_choices_to={"role": "student"},
        verbose_name="Студент",
    )
    answer = models.TextField("Ответ")
    submitted_at = models.DateTimeField(
        "Дата отправки",
        auto_now_add=True,
    )
    grade = models.PositiveSmallIntegerField(
        "Оценка",
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )
    teacher_comment = models.TextField(
        "Комментарий преподавателя",
        blank=True,
    )
    reviewed_at = models.DateTimeField(
        "Дата проверки",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Ответ студента"
        verbose_name_plural = "Ответы студентов"
        ordering = ["submitted_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "assignment"],
                name="unique_student_assignment",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(grade__isnull=True)
                    | models.Q(grade__gte=0, grade__lte=100)
                ),
                name="submission_grade_0_100",
            ),
        ]

    def __str__(self):
        return f"{self.student.username} — {self.assignment.title}"