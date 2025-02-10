def _is_image(reference):
    return (
        reference.endswith(".png")
        or reference.endswith(".jpg")
        or reference.endswith(".gif")
        or reference.endswith(".jpeg")
        or reference.endswith(".svg")
        or reference.endswith(".tiff")
        or reference.endswith(".webp")
    )


def _is_video(reference):
    return (
        reference.endswith(".mp4")
        or reference.endswith(".avi")
        or reference.endswith(".webm")
    )


def _is_pdf(reference):
    return reference.endswith(".pdf")
