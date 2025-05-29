from typing import Optional, List

from pydantic import BaseModel, Field

from src.models.menu_response_model import DeliveryMenuMeal


class Measure(BaseModel):
    measureKey: str
    measureUnit: str
    weight: str


class Product(BaseModel):
    name: str
    brand: Optional[str] = None
    barcode: Optional[float] = None
    energy: float
    fat: float
    saturatedFat: Optional[float] = None
    carbohydrate: float
    sugars: Optional[float] = None
    fiber: Optional[float] = None
    protein: float
    salt: Optional[float] = None
    animalProtein: Optional[float] = None
    vegetableProtein: Optional[float] = None
    monounsaturatedFat: Optional[float] = None
    polyunsaturatedFat: Optional[float] = None
    omega3: Optional[float] = None
    omega6: Optional[float] = None
    cholesterol: Optional[float] = None
    caffeine: Optional[float] = None
    vitaminA: Optional[float] = None
    vitaminB1: Optional[float] = None
    vitaminB2: Optional[float] = None
    vitaminB5: Optional[float] = None
    vitaminB6: Optional[float] = None
    vitaminB7: Optional[float] = None
    folicAcid: Optional[float] = None
    vitaminB12: Optional[float] = None
    vitaminC: Optional[float] = None
    vitaminD: Optional[float] = None
    vitaminE: Optional[float] = None
    vitaminPP: Optional[float] = None
    vitaminK: Optional[float] = None
    zinc: Optional[float] = None
    phosphorus: Optional[float] = None
    iodine: Optional[float] = None
    magnesium: Optional[float] = None
    copper: Optional[float] = None
    potassium: Optional[float] = None
    selenium: Optional[float] = None
    sodium: Optional[float] = None
    calcium: Optional[float] = None
    iron: Optional[float] = None
    measures: List[Measure]


def menu_meal_to_product(menu_meal: DeliveryMenuMeal, brand: str) -> Product:
    """
    Map a DeliveryMenuMeal (from menu_response_model) to a Product.
    """
    nutrition = menu_meal.nutrition

    # Compose measures from weight (if available)
    measures = []
    if hasattr(nutrition, "weight") and nutrition.weight:
        measures.append(Measure(
            measureKey="PACKAGE",
            measureUnit="g",
            weight=str(nutrition.weight)
        ))

    return Product(
        name=menu_meal.menuMealName,
        brand=brand,
        barcode=None,
        energy=nutrition.calories,
        fat=nutrition.fat,
        saturatedFat=nutrition.saturatedFattyAcids,
        carbohydrate=nutrition.carbohydrate,
        sugars=nutrition.sugar,
        fiber=nutrition.dietaryFiber,
        protein=nutrition.protein,
        salt=nutrition.salt,
        animalProtein=None,
        vegetableProtein=None,
        monounsaturatedFat=None,
        polyunsaturatedFat=None,
        omega3=None,
        omega6=None,
        cholesterol=None,
        caffeine=None,
        vitaminA=None,
        vitaminB1=None,
        vitaminB2=None,
        vitaminB5=None,
        vitaminB6=None,
        vitaminB7=None,
        folicAcid=None,
        vitaminB12=None,
        vitaminC=None,
        vitaminD=None,
        vitaminE=None,
        vitaminPP=None,
        vitaminK=None,
        zinc=None,
        phosphorus=None,
        iodine=None,
        magnesium=None,
        copper=None,
        potassium=None,
        selenium=None,
        sodium=None,
        calcium=None,
        iron=None,
        measures=measures
    )
