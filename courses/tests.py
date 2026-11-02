from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from .models import Assignment, Course, Enrollment, Lesson, Submission
from .video import get_video_data


User = get_user_model()


class PlatformTests(TestCase):
    PASSWORD = "Test-password-2026!"

    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(
            username="test_teacher",
            role="teacher",
        )
        cls.other_teacher = User.objects.create_user(
            username="test_other_teacher",
            role="teacher",
        )
        cls.student = User.objects.create_user(
            username="test_student",
            password=cls.PASSWORD,
            role="student",
        )
        cls.other_student = User.objects.create_user(
            username="test_other_student",
            role="student",
        )
        cls.outsider = User.objects.create_user(
            username="test_outsider",
            role="student",
        )

        cls.course = Course.objects.create(
            title="Published test course",
            description="Course description",
            teacher=cls.teacher,
            is_published=True,
        )
        cls.draft = Course.objects.create(
            title="Private draft course",
            description="Draft description",
            teacher=cls.teacher,
            is_published=False,
        )

        cls.lesson = Lesson.objects.create(
            course=cls.course,
            title="Test lesson",
            content="Protected lesson content",
            order=1,
            video_url="https://youtu.be/abcdefghijk",
        )

        cls.assignment = Assignment.objects.create(
            lesson=cls.lesson,
            title="Test assignment",
            description="Assignment description",
        )

        Enrollment.objects.create(
            student=cls.student,
            course=cls.course,
        )
        Enrollment.objects.create(
            student=cls.other_student,
            course=cls.course,
        )

    def _make_submission(self, **kwargs):
        return Submission.objects.create(
            assignment=self.assignment,
            student=self.student,
            answer="Private answer of the first student",
            **kwargs,
        )

    def test_catalog_hides_drafts(self):
        response = self.client.get(reverse("courses:course_list"))

        self.assertContains(response, self.course.title)
        self.assertNotContains(response, self.draft.title)

    def test_login_and_logout(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.student.username,
                "password": self.PASSWORD,
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:dashboard"),
            fetch_redirect_response=False,
        )

        response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 405)

        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(
            response,
            reverse("courses:course_list"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_anonymous_user_must_log_in_to_read_lesson(self):
        url = reverse("courses:lesson_detail", args=[self.lesson.pk])
        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
            fetch_redirect_response=False,
        )

    def test_lesson_access_by_role_and_enrollment(self):
        url = reverse("courses:lesson_detail", args=[self.lesson.pk])

        cases = [
            (self.student, 200),
            (self.teacher, 200),
            (self.outsider, 403),
            (self.other_teacher, 403),
        ]

        for user, expected_status in cases:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(url)

                self.assertEqual(response.status_code, expected_status)

                if expected_status == 200:
                    self.assertContains(response, self.lesson.content)
                    self.assertContains(response, "webinar-youtube")
                else:
                    self.assertNotContains(
                        response,
                        self.lesson.content,
                        status_code=403,
                    )
                    self.assertNotContains(
                        response,
                        "webinar-youtube",
                        status_code=403,
                    )

    def test_unpublished_course_and_lesson_are_hidden(self):
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("courses:course_detail", args=[self.draft.pk])
        )
        self.assertEqual(response.status_code, 404)

        self.lesson.course = self.draft
        self.lesson.save()

        response = self.client.get(
            reverse("courses:lesson_detail", args=[self.lesson.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_enrollment_requires_post_and_does_not_duplicate(self):
        self.client.force_login(self.outsider)
        url = reverse("courses:enroll_course", args=[self.course.pk])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertFalse(
            Enrollment.objects.filter(
                student=self.outsider,
                course=self.course,
            ).exists()
        )

        for attempt in range(2):
            response = self.client.post(url)
            self.assertEqual(response.status_code, 302)

        self.assertEqual(
            Enrollment.objects.filter(
                student=self.outsider,
                course=self.course,
            ).count(),
            1,
        )

    def test_teacher_cannot_enroll_as_student(self):
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("courses:enroll_course", args=[self.course.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Enrollment.objects.filter(student=self.teacher).exists()
        )

    def test_student_cannot_create_course(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("courses:course_create"),
            {
                "title": "Unauthorized course",
                "description": "Description",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Course.objects.filter(title="Unauthorized course").exists()
        )

    def test_course_owner_is_assigned_by_server(self):
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("courses:course_create"),
            {
                "title": "New teacher course",
                "description": "Description",
                "teacher": self.other_teacher.pk,
                "is_published": "on",
            },
        )

        self.assertEqual(response.status_code, 302)

        course = Course.objects.get(title="New teacher course")
        self.assertEqual(course.teacher, self.teacher)

        self.client.force_login(self.other_teacher)
        response = self.client.post(
            reverse("courses:course_edit", args=[course.pk]),
            {
                "title": "Changed by another teacher",
                "description": "Description",
            },
        )

        self.assertEqual(response.status_code, 404)

        course.refresh_from_db()
        self.assertEqual(course.title, "New teacher course")

    def test_course_deletion_requires_confirmation_post(self):
        self.client.force_login(self.teacher)
        url = reverse("courses:course_delete", args=[self.course.pk])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())

    def test_submission_owner_and_duplicate_protection(self):
        self.client.force_login(self.student)
        url = reverse(
            "courses:assignment_answer",
            args=[self.assignment.pk],
        )

        response = self.client.post(
            url,
            {
                "answer": "My original answer",
                "student": self.other_student.pk,
                "grade": 100,
            },
        )

        self.assertEqual(response.status_code, 302)

        submission = Submission.objects.get(assignment=self.assignment)
        self.assertEqual(submission.student, self.student)
        self.assertIsNone(submission.grade)

        self.client.post(url, {"answer": "Replacement answer"})

        self.assertEqual(
            Submission.objects.filter(
                assignment=self.assignment,
                student=self.student,
            ).count(),
            1,
        )

        submission.refresh_from_db()
        self.assertEqual(submission.answer, "My original answer")

    def test_unenrolled_student_cannot_submit_answer(self):
        self.client.force_login(self.outsider)

        response = self.client.post(
            reverse(
                "courses:assignment_answer",
                args=[self.assignment.pk],
            ),
            {"answer": "Unauthorized answer"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Submission.objects.filter(student=self.outsider).exists()
        )

    def test_student_cannot_see_another_students_answer(self):
        submission = self._make_submission()
        self.client.force_login(self.other_student)

        response = self.client.get(
            reverse(
                "courses:assignment_answer",
                args=[self.assignment.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["submission"])
        self.assertNotContains(response, submission.answer)

    def test_review_access_and_zero_grade(self):
        submission = self._make_submission()
        url = reverse("courses:submission_review", args=[submission.pk])

        for user, expected_status in [
            (self.student, 403),
            (self.other_teacher, 404),
        ]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.post(url, {"grade": 100})
                self.assertEqual(response.status_code, expected_status)

        submission.refresh_from_db()
        self.assertIsNone(submission.grade)

        self.client.force_login(self.teacher)
        response = self.client.post(
            url,
            {
                "grade": 0,
                "teacher_comment": "Please review the material",
            },
        )

        self.assertEqual(response.status_code, 302)

        submission.refresh_from_db()
        self.assertEqual(submission.grade, 0)
        self.assertIsNotNone(submission.reviewed_at)

        self.client.force_login(self.student)
        response = self.client.get(
            reverse(
                "courses:assignment_answer",
                args=[self.assignment.pk],
            )
        )
        self.assertContains(response, "0 / 100")
        self.assertContains(response, submission.teacher_comment)

    def test_invalid_grades_are_rejected(self):
        submission = self._make_submission()
        self.client.force_login(self.teacher)

        for grade in [-1, 101]:
            with self.subTest(grade=grade):
                response = self.client.post(
                    reverse(
                        "courses:submission_review",
                        args=[submission.pk],
                    ),
                    {"grade": grade},
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn("grade", response.context["form"].errors)

                submission.refresh_from_db()
                self.assertIsNone(submission.grade)

    def test_reviewed_answer_cannot_be_replaced(self):
        submission = self._make_submission(
            grade=80,
            teacher_comment="Original comment",
        )
        self.client.force_login(self.student)

        response = self.client.post(
            reverse(
                "courses:assignment_answer",
                args=[self.assignment.pk],
            ),
            {
                "answer": "Changed answer",
                "grade": 100,
                "teacher_comment": "Changed comment",
            },
        )

        self.assertEqual(response.status_code, 302)

        submission.refresh_from_db()
        self.assertEqual(
            submission.answer,
            "Private answer of the first student",
        )
        self.assertEqual(submission.grade, 80)
        self.assertEqual(submission.teacher_comment, "Original comment")

    def test_enrollment_without_csrf_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.outsider)

        response = csrf_client.post(
            reverse("courses:enroll_course", args=[self.course.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Enrollment.objects.filter(student=self.outsider).exists()
        )


class VideoTests(SimpleTestCase):
    def test_supported_video_links(self):
        links = {
            "https://youtu.be/abcdefghijk": "youtube",
            "https://www.youtube.com/watch?v=abcdefghijk": "youtube",
            (
                "https://rutube.ru/video/"
                "0123456789abcdef0123456789abcdef/"
            ): "rutube",
            "https://vimeo.com/123456789": "vimeo",
        }

        for link, provider in links.items():
            with self.subTest(link=link):
                self.assertEqual(
                    get_video_data(link)["provider"],
                    provider,
                )

    def test_unsupported_video_links_are_rejected(self):
        links = [
            "javascript:alert(1)",
            "https://example.com/video",
            "https://youtube.com.example.com/watch?v=abcdefghijk",
            "https://youtube.com@evil.example/watch?v=abcdefghijk",
        ]

        for link in links:
            with self.subTest(link=link):
                with self.assertRaises(ValueError):
                    get_video_data(link)

    def test_video_is_optional(self):
        self.assertIsNone(get_video_data(""))