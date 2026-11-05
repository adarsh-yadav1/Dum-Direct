"""Dish photos, linked from their source instead of stored in the repository.

Add one entry per dish: the dish name mapped to a direct https link to the image. Only hosts
whose licence allows linking are accepted (Unsplash, Pexels, Wikimedia Commons). Credit each
photographer in ASSETS.md. A dish with no entry is shown with a plain tile in the app.
"""

IMAGE_URLS: dict[str, str] = {}

ALLOWED_IMAGE_HOSTS = frozenset({"images.unsplash.com", "images.pexels.com", "upload.wikimedia.org"})
