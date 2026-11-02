import re
from urllib.parse import parse_qs, urlencode, urlsplit


def get_video_data(url):
    if not url:
        return None

    error = (
        "Укажите корректную HTTPS-ссылку на видео "
        "YouTube, Rutube или Vimeo."
    )

    try:
        parsed = urlsplit(url.strip())
    except ValueError as exc:
        raise ValueError(error) from exc

    if parsed.scheme != "https":
        raise ValueError(error)

    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    query = parse_qs(parsed.query)

    youtube_hosts = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }

    if host in youtube_hosts or host in {"youtu.be", "www.youtu.be"}:
        if host in {"youtu.be", "www.youtu.be"}:
            video_id = path
        elif path == "watch":
            video_id = query.get("v", [""])[0]
        else:
            match = re.fullmatch(
                r"(?:embed|shorts|live)/([\w-]{11})",
                path,
            )
            video_id = match.group(1) if match else ""

        if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return {
                "provider": "youtube",
                "video_id": video_id,
            }

    elif host in {"rutube.ru", "www.rutube.ru"}:
        match = re.fullmatch(
            r"(?:video/(?:private/)?|play/embed/)([a-fA-F0-9]{32})",
            path,
        )

        if match:
            params = {
                "autoplay": "false",
                "autostartmute": "true",
            }

            if query.get("p"):
                params["p"] = query["p"][0]

            return {
                "provider": "rutube",
                "embed_url": (
                    f"https://rutube.ru/play/embed/{match.group(1)}/?"
                    + urlencode(params)
                ),
            }

    elif host in {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}:
        match = re.fullmatch(
            r"(?:video/)?([0-9]{1,12})(?:/([a-fA-F0-9]+))?",
            path,
        )

        if match:
            params = {
                "autoplay": "0",
                "muted": "1",
                "dnt": "1",
            }

            private_hash = query.get("h", [""])[0] or match.group(2)

            if private_hash:
                params["h"] = private_hash

            return {
                "provider": "vimeo",
                "embed_url": (
                    f"https://player.vimeo.com/video/{match.group(1)}?"
                    + urlencode(params)
                ),
            }

    raise ValueError(error)