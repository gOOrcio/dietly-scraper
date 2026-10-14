from src.models.add_product_model import (
    clean_meal_name,
    convert_menu_meal_to_nutrition_product,
)
from src.models.menu_response_model import DeliveryMenuMeal
from src.utils.constants import FITATU_MAX_PRODUCT_NAME_LENGTH

GRAMATURA_NAME = (
    '"Rustykalny Gulasz"mięso duszone w sosie burgundzkim z pieczarkami  podany z '
    "kaszą gryczaną ALERGENY gorczyca SKŁADNIKI łopatka wieprzowa,oliwa,cebula"
)


def test_clean_meal_name_strips_allergen_and_ingredient_tail():
    assert clean_meal_name(GRAMATURA_NAME) == (
        '"Rustykalny Gulasz"mięso duszone w sosie burgundzkim z pieczarkami podany '
        "z kaszą gryczaną"
    )


def test_clean_meal_name_strips_ingredients_without_allergens():
    assert clean_meal_name("Zupa krem SKŁADNIKI dynia, śmietana") == "Zupa krem"


def test_clean_meal_name_leaves_short_names_alone_except_whitespace():
    assert clean_meal_name(" Brownie z  malinowym musem ") == (
        "Brownie z malinowym musem"
    )


def test_clean_meal_name_caps_length():
    assert len(clean_meal_name("x" * 400)) == FITATU_MAX_PRODUCT_NAME_LENGTH


def test_clean_meal_name_never_returns_empty():
    assert clean_meal_name("ALERGENY gluten") == "ALERGENY gluten"


def _meal(nutrition):
    return DeliveryMenuMeal(
        mealName="Obiad",
        menuMealName=GRAMATURA_NAME,
        deliveryMealId=1,
        nutrition=nutrition,
    )


def test_convert_maps_dietly_nutrition_to_fitatu_fields():
    product = convert_menu_meal_to_nutrition_product(
        _meal(
            dict(
                weight=350,
                calories=520.5,
                fat=20,
                protein=30,
                carbohydrate=50,
                dietaryFiber=5,
                sugar=3,
                salt=1.2,
                saturatedFattyAcids=6,
            )
        ),
        "GRAMATURA",
    )
    assert product.name.endswith("z kaszą gryczaną")
    assert product.brand == "GRAMATURA"
    assert (product.energy, product.fat, product.protein, product.carbohydrate) == (
        520.5,
        20,
        30,
        50,
    )
    assert (product.fiber, product.sugars, product.salt, product.saturatedFat) == (
        5,
        3,
        1.2,
        6,
    )
    assert [m.weight for m in product.measures] == ["350.0"]
    assert product.vitaminC is None


def test_convert_without_nutrition_posts_placeholder_macros():
    product = convert_menu_meal_to_nutrition_product(_meal(None), "UrbanFits")
    assert (product.energy, product.fat, product.protein, product.carbohydrate) == (
        0,
        0,
        0,
        0,
    )
    assert [m.weight for m in product.measures] == ["100"]
