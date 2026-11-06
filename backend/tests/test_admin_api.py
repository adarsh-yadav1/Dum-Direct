import pytest
from tests.test_kitchen_api import as_user, staff  # noqa: F401
from tests.test_menu import locate
from tests.test_orders_api import body, noon, place, seeded, variant  # noqa: F401


@pytest.fixture()
def admin(client, engine, staff):  # noqa: F811
    as_user(client, "admin@example.com")
    return client


def shown(client, engine, place_name="Kondapur"):
    """Dish name -> item, as customers see the menu at a place."""
    menu = client.get("/menu", params=locate(engine, place_name)).json()
    return {i["name"]: i for c in menu["categories"] for i in c["items"]}


def find(client, name):
    menu = client.get("/admin/menu").json()
    return next(i for c in menu["categories"] for i in c["items"] if i["name"] == name)


# --- access -----------------------------------------------------------------------------------


def test_only_admins_can_use_the_menu_admin(client, engine, staff):
    assert client.get("/admin/menu").status_code == 401
    for email in ["cust@example.com", "chef@example.com", "manager@example.com"]:
        as_user(client, email)
        assert client.get("/admin/menu").status_code == 403
        assert client.patch("/admin/variants/1", json={"price_paise": 5000}).status_code == 403
        assert client.post("/admin/items", json={}).status_code == 403
    as_user(client, "admin@example.com")
    assert client.get("/admin/menu").status_code == 200


def test_full_menu_shows_every_outlet_listing(admin):
    menu = admin.get("/admin/menu").json()
    assert menu["cities"] == ["Bengaluru", "Hyderabad"] and len(menu["outlets"]) == 4
    qubani = find(admin, "Qubani ka meetha")
    kondapur = next(o for o in menu["outlets"] if o["name"] == "Kondapur")["id"]
    assert next(o for o in qubani["outlets"] if o["outlet_id"] == kondapur) == {
        "outlet_id": kondapur, "listed": True, "is_available": False}
    chai = find(admin, "Irani chai")
    gachibowli = next(o for o in menu["outlets"] if o["name"].startswith("Gachibowli"))["id"]
    assert next(o for o in chai["outlets"] if o["outlet_id"] == gachibowli)["listed"] is False


# --- prices -----------------------------------------------------------------------------------


def test_a_price_change_reaches_the_customer_menu(admin, engine):
    portion = find(admin, "Veg biryani")["variants"][0]
    assert admin.patch(f"/admin/variants/{portion['id']}", json={"price_paise": 29900}).json()["price_paise"] == 29900
    assert shown(admin, engine)["Veg biryani"]["variants"][0]["price_paise"] == 29900


@pytest.mark.parametrize("payload", [{"price_paise": 99}, {"price_paise": 1_000_001}, {"price_paise": "x"}, {"price_paise": 5000, "serves": 9}, {}])
def test_bad_prices_are_rejected(admin, payload):
    portion_id = find(admin, "Veg biryani")["variants"][0]["id"]
    assert admin.patch(f"/admin/variants/{portion_id}", json=payload).status_code == 422
    assert admin.patch("/admin/variants/999999", json={"price_paise": 5000}).status_code == 404


def test_city_prices_apply_only_to_that_city_and_can_be_cleared(admin, engine):
    portion = find(admin, "Veg biryani")["variants"][0]
    base = portion["price_paise"]
    url = f"/admin/variants/{portion['id']}/city-prices/Hyderabad"
    assert admin.put(url, json={"price_paise": 31000}).status_code == 200
    assert shown(admin, engine, "Kondapur")["Veg biryani"]["variants"][0]["price_paise"] == 31000
    assert shown(admin, engine, "Indiranagar")["Veg biryani"]["variants"][0]["price_paise"] != 31000
    assert admin.delete(url).status_code == 204
    assert shown(admin, engine, "Kondapur")["Veg biryani"]["variants"][0]["price_paise"] == base
    assert admin.delete(url).status_code == 204  # clearing twice is harmless
    assert admin.put(f"/admin/variants/{portion['id']}/city-prices/Atlantis", json={"price_paise": 5000}).status_code == 404


# --- what is offered where --------------------------------------------------------------------


def test_unlisting_a_dish_removes_it_and_reroutes_orders(admin, engine, noon):
    item = find(admin, "Veg biryani")
    kondapur = next(o for o in admin.get("/admin/menu").json()["outlets"] if o["name"] == "Kondapur")["id"]
    assert admin.put(f"/admin/outlets/{kondapur}/items/{item['id']}", json={"listed": False}).json()["listed"] is False
    assert "Veg biryani" not in shown(admin, engine)
    as_user(admin, "cust@example.com")
    order = place(admin, body(engine, [{"variant_id": item["variants"][0]["id"], "qty": 1}])).json()
    assert order["outlet"]["name"] != "Kondapur" and order["rerouted_from"] == "Kondapur"
    as_user(admin, "admin@example.com")
    admin.put(f"/admin/outlets/{kondapur}/items/{item['id']}", json={"listed": True})
    admin.put(f"/admin/outlets/{kondapur}/items/{item['id']}", json={"listed": True})  # idempotent
    assert shown(admin, engine)["Veg biryani"]["orderable"] is True
    assert admin.put("/admin/outlets/999/items/1", json={"listed": True}).status_code == 404
    assert admin.put(f"/admin/outlets/{kondapur}/items/999999", json={"listed": True}).status_code == 404


def test_deactivating_a_dish_hides_it_everywhere_and_blocks_orders(admin, engine, noon):
    item = find(admin, "Veg biryani")
    assert admin.patch(f"/admin/items/{item['id']}", json={"is_active": False}).json()["is_active"] is False
    assert "Veg biryani" not in shown(admin, engine)
    as_user(admin, "cust@example.com")
    refused = place(admin, body(engine, [{"variant_id": item["variants"][0]["id"], "qty": 1}]))
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "unknown_dish"


# --- editing and creating dishes --------------------------------------------------------------


def test_edit_details_and_image_rules(admin, engine):
    item = find(admin, "Veg biryani")
    ok = "https://images.unsplash.com/photo-1234?w=400"
    assert admin.patch(f"/admin/items/{item['id']}", json={"description": "New text", "image_url": ok}).status_code == 200
    assert shown(admin, engine)["Veg biryani"]["image_url"] == ok
    assert admin.patch(f"/admin/items/{item['id']}", json={"image_url": None}).status_code == 200
    assert shown(admin, engine)["Veg biryani"]["image_url"] is None
    for bad in ["http://images.unsplash.com/x.jpg", "https://evil.example.com/x.jpg", "javascript:alert(1)", "https://images.unsplash.com/" + "a" * 300]:
        assert admin.patch(f"/admin/items/{item['id']}", json={"image_url": bad}).status_code == 422
    other = find(admin, "Chicken dum biryani")["name"]
    assert admin.patch(f"/admin/items/{item['id']}", json={"name": other}).status_code == 409
    assert admin.patch("/admin/items/999999", json={"name": "Nothing"}).status_code == 404
    assert admin.patch(f"/admin/items/{item['id']}", json={"is_veg": False}).status_code == 422


def new_dish(admin, **over):
    with_category = next(c for c in admin.get("/admin/menu").json()["categories"] if c["name"] == "Biryani")["id"]
    payload = {"category_id": with_category, "name": "Hyderabadi egg biryani", "is_veg": False, "spice_level": 2,
               "allergens": ["egg"], "base_prep_minutes": 25, "description": "Boiled eggs on dum rice.",
               "variants": [{"label": "Regular", "serves": 1, "price_paise": 24000}, {"label": "Large", "serves": 2, "price_paise": 42000}]}
    return admin.post("/admin/items", json={**payload, **over})


def test_a_new_dish_appears_only_where_it_is_listed(admin, engine, noon):
    created = new_dish(admin)
    assert created.status_code == 201
    assert "Hyderabadi egg biryani" not in shown(admin, engine)
    kondapur = next(o for o in admin.get("/admin/menu").json()["outlets"] if o["name"] == "Kondapur")["id"]
    admin.put(f"/admin/outlets/{kondapur}/items/{created.json()['id']}", json={"listed": True})
    dish = shown(admin, engine)["Hyderabadi egg biryani"]
    assert [v["price_paise"] for v in dish["variants"]] == [24000, 42000] and dish["allergens"] == ["egg"]
    as_user(admin, "cust@example.com")
    assert place(admin, body(engine, [{"variant_id": dish["variants"][0]["id"], "qty": 1}])).status_code == 201


@pytest.mark.parametrize(
    "over",
    [{"variants": []}, {"name": "x"}, {"spice_level": 4}, {"base_prep_minutes": 0},
     {"variants": [{"label": "A", "serves": 1, "price_paise": 5000}, {"label": "a", "serves": 2, "price_paise": 9000}]},
     {"variants": [{"label": "A", "serves": 0, "price_paise": 5000}]}, {"allergens": ["x"] * 11}, {"extra": 1}],
)
def test_invalid_new_dishes_are_rejected(admin, over):
    assert new_dish(admin, **over).status_code == 422


def test_new_dish_needs_a_real_category_and_a_new_name(admin):
    assert new_dish(admin, category_id=99999).status_code == 404
    assert new_dish(admin, name="Veg biryani").status_code == 409
    assert new_dish(admin).status_code == 201 and new_dish(admin).status_code == 409
