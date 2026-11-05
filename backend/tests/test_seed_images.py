from urllib.parse import urlparse

from app.seed.catalog_data import ITEMS
from app.seed.images import ALLOWED_IMAGE_HOSTS, IMAGE_URLS


def test_every_image_belongs_to_a_real_dish():
    assert set(IMAGE_URLS) <= {item.name for item in ITEMS}


def test_every_image_is_an_https_link_on_an_allowed_host():
    for name, url in IMAGE_URLS.items():
        parts = urlparse(url)
        assert parts.scheme == "https" and parts.hostname in ALLOWED_IMAGE_HOSTS, name
