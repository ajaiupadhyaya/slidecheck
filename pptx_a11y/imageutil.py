def image_bytes_and_type(picture):
    """Return (bytes, media_type) for a Picture shape, or None if unavailable."""
    try:
        img = picture.image
        return img.blob, img.content_type
    except Exception:  # noqa: BLE001
        return None
