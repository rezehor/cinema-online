import re
from PIL import Image
from io import BytesIO
from fastapi import UploadFile

from Cinema.models.users import GenderEnum


def validate_name(name: str):
    if re.search(r'^[A-Za-z]*$', name) is None:
        raise ValueError(f'{name} contains non-english letters')


def validate_image(avatar: UploadFile) -> None:
    supported_image_formats = ["JPG", "JPEG", "PNG"]
    max_file_size = 1 * 1024 * 1024

    contents = avatar.file.read()
    if len(contents) > max_file_size:
        raise ValueError("Image size exceeds 1 MB")

    try:
        image = Image.open(BytesIO(contents))
        avatar.file.seek(0)
        image_format = image.format
        if image_format not in supported_image_formats:
            raise ValueError(f"Unsupported image format: {image_format}. Use one of next: {supported_image_formats}")
    except IOError:
        raise ValueError("Invalid image format")


def validate_gender(gender: str) -> None:
    if gender not in GenderEnum.__members__.values():
        raise ValueError(f"Gender must be one of: {', '.join(g.value for g in GenderEnum)}")
