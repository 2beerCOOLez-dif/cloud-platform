from django.core.exceptions import ValidationError

from .video import get_video_data


def validate_video_url(value):
    try:
        get_video_data(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc