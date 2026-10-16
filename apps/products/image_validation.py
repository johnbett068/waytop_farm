"""Validate catalog photography using file contents, not its claimed MIME type."""
from pathlib import PurePosixPath
import warnings

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 15 * 1024 * 1024
IMAGE_EXTENSIONS = {"JPEG": {".jpg", ".jpeg"}, "PNG": {".png"}, "WEBP": {".webp"}, "GIF": {".gif"}}


def validate_product_image(upload):
    if upload.size > MAX_IMAGE_BYTES:
        raise ValidationError("Choose an image no larger than 15 MB.", code="image_too_large")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            upload.seek(0)
            with Image.open(upload) as picture:
                image_format = picture.format
                picture.verify()
            upload.seek(0)
            with Image.open(upload) as picture:
                picture.load()
        extension = PurePosixPath(upload.name).suffix.lower()
        if image_format not in IMAGE_EXTENSIONS or extension not in IMAGE_EXTENSIONS[image_format]:
            raise ValidationError("Use a JPEG, PNG, WebP or GIF image with its matching file extension.")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValidationError("Upload a valid, undamaged image.", code="invalid_image") from error
    finally:
        upload.seek(0)


def product_image_upload_path(instance, filename):
    extension = PurePosixPath(filename).suffix.lower()
    return f"products/{instance.product_id}/{instance.id.hex}{extension}"
