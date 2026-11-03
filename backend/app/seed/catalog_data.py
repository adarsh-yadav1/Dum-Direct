"""Sample catalogue: outlets, localities and menu, as plain data.

Prices are whole rupees here and converted to paise on load. All prices include
5% GST. Nothing below is real: names of the first three outlets come from the
client brief, everything else is invented for the demo.
"""

from dataclasses import dataclass, field
from datetime import time
from typing import Any

BASE_CITY = "Hyderabad"

# Other cities price every variant as a percentage of the base price, rounded to Rs 5.
# This exists to demonstrate the "prices by city" feature of the menu admin.
CITY_PRICE_PERCENT = {"Bengaluru": 110}

# Illustrative coordinates and radii (assumption A2). They are chosen so the demo shows:
#   HITEC City   -> served by Kondapur and the Gachibowli cloud kitchen (nearest wins)
#   Madhapur     -> served by three outlets
#   Miyapur      -> served by Kondapur only
#   Manikonda    -> served by the cloud kitchen only, near the edge of its radius
#   Secunderabad -> served by nobody ("not serviceable")
OUTLETS: list[dict[str, Any]] = [
    {
        "name": "Kondapur",
        "kind": "outlet",
        "city": "Hyderabad",
        "locality": "Kondapur",
        "address_line": "Sample address, Kondapur Main Road",
        "latitude": 17.4600,
        "longitude": 78.3650,
        "delivery_radius_km": 5.0,
        "fssai_no": "99999000000101",
        "min_prep_minutes": 20,
        "capacity_units_per_hour": 60,
    },
    {
        "name": "Gachibowli cloud kitchen",
        "kind": "cloud_kitchen",
        "city": "Hyderabad",
        "locality": "Gachibowli",
        "address_line": "Sample address, Gachibowli",
        "latitude": 17.4400,
        "longitude": 78.3480,
        "delivery_radius_km": 6.0,
        "fssai_no": "99999000000102",
        "min_prep_minutes": 25,
        "capacity_units_per_hour": 90,
    },
    {
        "name": "Kukatpally",
        "kind": "outlet",
        "city": "Hyderabad",
        "locality": "Kukatpally",
        "address_line": "Sample address, Kukatpally Housing Board",
        "latitude": 17.4850,
        "longitude": 78.4130,
        "delivery_radius_km": 5.0,
        "fssai_no": "99999000000103",
        "min_prep_minutes": 20,
        "capacity_units_per_hour": 60,
    },
    {
        # Invented (assumption A1): the brief names no outlet outside Hyderabad. It exists
        # so that city-based pricing has something to apply to.
        "name": "Indiranagar",
        "kind": "outlet",
        "city": "Bengaluru",
        "locality": "Indiranagar",
        "address_line": "Sample address, Indiranagar",
        "latitude": 12.9780,
        "longitude": 77.6400,
        "delivery_radius_km": 5.0,
        "fssai_no": "99999000000104",
        "min_prep_minutes": 20,
        "capacity_units_per_hour": 50,
    },
]

# Places for the location search (assumption A3): name, city, latitude, longitude.
LOCALITIES: list[tuple[str, str, float, float]] = [
    ("Kondapur", "Hyderabad", 17.4600, 78.3650),
    ("Gachibowli", "Hyderabad", 17.4400, 78.3480),
    ("Kukatpally", "Hyderabad", 17.4850, 78.4130),
    ("Madhapur", "Hyderabad", 17.4480, 78.3910),
    ("HITEC City", "Hyderabad", 17.4430, 78.3770),
    ("Miyapur", "Hyderabad", 17.4970, 78.3590),
    ("Manikonda", "Hyderabad", 17.4030, 78.3870),
    ("Financial District", "Hyderabad", 17.4170, 78.3400),
    ("Jubilee Hills", "Hyderabad", 17.4320, 78.4070),
    ("Banjara Hills", "Hyderabad", 17.4130, 78.4390),
    ("Ameerpet", "Hyderabad", 17.4370, 78.4480),
    ("Begumpet", "Hyderabad", 17.4440, 78.4630),
    ("Secunderabad", "Hyderabad", 17.4400, 78.4980),
    ("LB Nagar", "Hyderabad", 17.3480, 78.5520),
    ("Indiranagar", "Bengaluru", 12.9780, 77.6400),
    ("Koramangala", "Bengaluru", 12.9350, 77.6240),
]

# name, sort order, daily window (wall-clock IST). Haleem is only sold in the evening.
CATEGORIES: list[tuple[str, int, time | None, time | None]] = [
    ("Biryani", 1, None, None),
    ("Starters", 2, None, None),
    ("Curries and sides", 3, None, None),
    ("Haleem", 4, time(16, 0), time(23, 30)),
    ("Desserts", 5, None, None),
    ("Drinks", 6, None, None),
]

ALLERGEN_VOCABULARY = frozenset({"milk", "egg", "gluten", "peanut", "sesame", "tree nuts"})


@dataclass(frozen=True)
class ItemSpec:
    name: str
    category: str
    is_veg: bool
    spice_level: int  # 0 mild .. 3 very hot
    allergens: tuple[str, ...]
    prep_minutes: int
    description: str
    variants: tuple[tuple[str, int, int], ...]  # (label, price in rupees, serves)
    addons: tuple[tuple[str, int], ...] = field(default_factory=tuple)  # (name, price in rupees)


_BIRYANI_ADDONS = (("Extra raita", 30), ("Boiled egg", 25), ("Extra mirchi ka salan", 40))
_VEG_BIRYANI_ADDONS = (("Extra raita", 30), ("Extra mirchi ka salan", 40))

ITEMS: list[ItemSpec] = [
    ItemSpec(
        "Chicken dum biryani", "Biryani", False, 2, ("milk",), 25,
        "Basmati and marinated chicken, sealed and slow-cooked on dum.",
        (("Regular", 320, 1), ("Large", 560, 2), ("Family pack", 990, 4)),
        _BIRYANI_ADDONS,
    ),
    ItemSpec(
        "Mutton dum biryani", "Biryani", False, 2, ("milk",), 30,
        "Tender mutton layered with saffron rice, cooked on dum.",
        (("Regular", 420, 1), ("Large", 760, 2), ("Family pack", 1390, 4)),
        _BIRYANI_ADDONS,
    ),
    ItemSpec(
        "Veg biryani", "Biryani", True, 1, ("milk",), 20,
        "Seasonal vegetables and fragrant rice, finished with fried onions.",
        (("Regular", 250, 1), ("Large", 450, 2), ("Family pack", 790, 4)),
        _VEG_BIRYANI_ADDONS,
    ),
    ItemSpec(
        "Paneer dum biryani", "Biryani", True, 1, ("milk",), 22,
        "Marinated paneer and basmati, sealed and cooked slowly.",
        (("Regular", 290, 1), ("Large", 520, 2)),
        _VEG_BIRYANI_ADDONS,
    ),
    ItemSpec(
        "Chicken 65", "Starters", False, 3, ("egg", "milk"), 15,
        "Crisp, spiced fried chicken with curry leaf and green chilli.",
        (("Half", 220, 1), ("Full", 380, 2)),
    ),
    ItemSpec(
        "Paneer 65", "Starters", True, 2, ("milk",), 15,
        "Crisp paneer in a hot, tangy coating.",
        (("Half", 200, 1), ("Full", 340, 2)),
    ),
    ItemSpec(
        "Mutton seekh kebab", "Starters", False, 2, (), 18,
        "Minced mutton skewers grilled over charcoal.",
        (("4 pieces", 360, 2),),
    ),
    ItemSpec(
        "Mirchi ka salan", "Curries and sides", True, 2, ("peanut", "sesame"), 10,
        "Green chillies in a tangy peanut, sesame and tamarind gravy.",
        (("Regular", 140, 1),),
    ),
    ItemSpec(
        "Bagara baingan", "Curries and sides", True, 2, ("peanut", "sesame"), 10,
        "Baby aubergines in a rich peanut and sesame gravy.",
        (("Regular", 140, 1),),
    ),
    ItemSpec(
        "Burani raita", "Curries and sides", True, 0, ("milk",), 3,
        "Cool garlic yoghurt, the traditional partner to biryani.",
        (("Regular", 60, 1),),
    ),
    ItemSpec(
        "Dalcha", "Curries and sides", True, 1, (), 10,
        "Lentils cooked with tamarind and gentle spice.",
        (("Regular", 150, 1),),
    ),
    ItemSpec(
        "Rumali roti", "Curries and sides", True, 0, ("gluten",), 4,
        "Paper-thin handkerchief bread.",
        (("1 piece", 30, 1),),
    ),
    ItemSpec(
        "Mutton haleem", "Haleem", False, 2, ("gluten", "milk"), 12,
        "Slow-cooked mutton, wheat and lentils, served with fried onions.",
        (("Regular", 350, 1), ("Large", 560, 2)),
        (("Extra ghee", 20), ("Fried onions", 15)),
    ),
    ItemSpec(
        "Double ka meetha", "Desserts", True, 0, ("gluten", "milk", "tree nuts"), 5,
        "Fried bread soaked in saffron milk and topped with nuts.",
        (("Regular", 95, 1),),
    ),
    ItemSpec(
        "Qubani ka meetha", "Desserts", True, 0, ("milk", "tree nuts"), 5,
        "Stewed apricots with cream.",
        (("Regular", 110, 1),),
    ),
    ItemSpec(
        "Irani chai", "Drinks", True, 0, ("milk",), 5,
        "Strong, sweet, milky tea.",
        (("Cup", 40, 1),),
    ),
    ItemSpec(
        "Masala chaas", "Drinks", True, 1, ("milk",), 3,
        "Spiced buttermilk with mint and cumin.",
        (("Glass", 60, 1),),
    ),
    ItemSpec(
        "Mint lemonade", "Drinks", True, 0, (), 4,
        "Fresh lime and mint over ice.",
        (("Glass", 70, 1),),
    ),
]

# (outlet name, item name) pairs. A paused item is offered but out of stock right now,
# which is the data the "outlet marks an item out of stock" demo needs.
PAUSED: frozenset[tuple[str, str]] = frozenset({("Kondapur", "Qubani ka meetha")})
# An item an outlet does not offer at all (no availability row).
NOT_OFFERED: frozenset[tuple[str, str]] = frozenset({("Gachibowli cloud kitchen", "Irani chai")})
