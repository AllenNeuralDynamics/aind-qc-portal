def _is_image(reference):
    return (
        reference.endswith(".png")
        or reference.endswith(".jpg")  # noqa: W503
        or reference.endswith(".gif")  # noqa: W503
        or reference.endswith(".jpeg")  # noqa: W503
        or reference.endswith(".svg")  # noqa: W503
        or reference.endswith(".tiff")  # noqa: W503
        or reference.endswith(".webp")  # noqa: W503
    )


def _is_video(reference):
    return reference.endswith(".mp4") or reference.endswith(".avi") or reference.endswith(".webm")


def _is_pdf(reference):
    return reference.endswith(".pdf")
