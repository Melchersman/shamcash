"""Smoke-test an installed wheel without the QR extra or source checkout."""

import importlib.metadata
import json
import pkgutil
import sys
from pathlib import Path

import httpx
import shamcash

source = Path(sys.argv[1]).resolve()
assert source not in Path(shamcash.__file__).resolve().parents
assert shamcash.__version__ == importlib.metadata.version("shamcash")
assert pkgutil.get_data("shamcash", "py.typed") is not None
assert pkgutil.get_data("shamcash", "assets/shamcash_logo.png")
assert pkgutil.get_data("shamcash", "assets/shamcash_logo.svg")
for dependency in ("PIL", "qrcode", "cairosvg"):
    assert dependency not in sys.modules
png = b"\x89PNG\r\n\x1a\nimage"


def handler(request):
    assert request.headers["Authorization"] == "Bearer smoke-token"
    if request.url.path.endswith("/qr"):
        return httpx.Response(200, content=png, headers={"Content-Type": "image/png"})
    return httpx.Response(
        200,
        json={
            "status": "success",
            "data": {
                "plans": [
                    {
                        "id": "monthly",
                        "code": "monthly",
                        "name": "Monthly",
                        "price_usd": "1.5",
                        "duration_days": 30,
                        "base_price_usd": "2",
                        "discount_percent": "25",
                    }
                ]
            },
        },
    )


with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
    with shamcash.ShamCashAPISync("smoke-token", client=transport) as api:
        assert str(api.list_plans()[0].price_usd) == "1.5"
        assert api.get_link_qr("link_1") == png
print(
    "Installed wheel imports, models, HTTP methods, typed marker and assets verified without QR extras"
)
