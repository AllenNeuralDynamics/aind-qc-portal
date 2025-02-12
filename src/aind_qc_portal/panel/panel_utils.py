""" Panel utilities """


def reference_is_image(reference):
    """ Check if the reference is an image """
    return (
        reference.endswith(".png")
        or reference.endswith(".jpg")  # noqa: W503
        or reference.endswith(".gif")  # noqa: W503
        or reference.endswith(".jpeg")  # noqa: W503
        or reference.endswith(".svg")  # noqa: W503
        or reference.endswith(".tiff")  # noqa: W503
        or reference.endswith(".webp")  # noqa: W503
    )


def reference_is_video(reference):
    """ Check if the reference is a video """
    return reference.endswith(".mp4") or reference.endswith(".avi") or reference.endswith(".webm")


def reference_is_pdf(reference):
    """ Check if the reference is a pdf """
    return reference.endswith(".pdf")
