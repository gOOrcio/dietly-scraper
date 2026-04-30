from typing import Optional, List

from pydantic import BaseModel, Field

from src.models.menu_response_model import DeliveryMenuMeal


class NutritionMeasure(BaseModel):
    """Represents a nutrition measurement unit."""

    measureKey: str = Field(description="Measurement key identifier")
    measureUnit: str = Field(description="Unit of measurement (e.g., 'g', 'ml')")
    weight: str = Field(description="Weight value as string")


class NutritionProduct(BaseModel):
    """Represents a complete nutrition product for Fitatu API."""

    name: str = Field(description="Product name")
    brand: Optional[str] = Field(default=None, description="Product brand")
    barcode: Optional[float] = Field(default=None, description="Product barcode")

    # Basic nutrition values (required)
    energy: float = Field(description="Energy content in calories")
    fat: float = Field(description="Fat content in grams")
    carbohydrate: float = Field(description="Carbohydrate content in grams")
    protein: float = Field(description="Protein content in grams")

    # Detailed nutrition values (optional)
    saturatedFat: Optional[float] = Field(
        default=None, description="Saturated fat in grams"
    )
    sugars: Optional[float] = Field(default=None, description="Sugar content in grams")
    fiber: Optional[float] = Field(default=None, description="Dietary fiber in grams")
    salt: Optional[float] = Field(default=None, description="Salt content in grams")

    # Protein breakdown
    animalProtein: Optional[float] = Field(
        default=None, description="Animal protein in grams"
    )
    vegetableProtein: Optional[float] = Field(
        default=None, description="Vegetable protein in grams"
    )

    # Fat breakdown
    monounsaturatedFat: Optional[float] = Field(
        default=None, description="Monounsaturated fat in grams"
    )
    polyunsaturatedFat: Optional[float] = Field(
        default=None, description="Polyunsaturated fat in grams"
    )
    omega3: Optional[float] = Field(
        default=None, description="Omega-3 fatty acids in grams"
    )
    omega6: Optional[float] = Field(
        default=None, description="Omega-6 fatty acids in grams"
    )
    cholesterol: Optional[float] = Field(
        default=None, description="Cholesterol in milligrams"
    )

    # Other compounds
    caffeine: Optional[float] = Field(
        default=None, description="Caffeine in milligrams"
    )

    # Vitamins
    vitaminA: Optional[float] = Field(
        default=None, description="Vitamin A in micrograms"
    )
    vitaminB1: Optional[float] = Field(
        default=None, description="Vitamin B1 in milligrams"
    )
    vitaminB2: Optional[float] = Field(
        default=None, description="Vitamin B2 in milligrams"
    )
    vitaminB5: Optional[float] = Field(
        default=None, description="Vitamin B5 in milligrams"
    )
    vitaminB6: Optional[float] = Field(
        default=None, description="Vitamin B6 in milligrams"
    )
    vitaminB7: Optional[float] = Field(
        default=None, description="Vitamin B7 in micrograms"
    )
    folicAcid: Optional[float] = Field(
        default=None, description="Folic acid in micrograms"
    )
    vitaminB12: Optional[float] = Field(
        default=None, description="Vitamin B12 in micrograms"
    )
    vitaminC: Optional[float] = Field(
        default=None, description="Vitamin C in milligrams"
    )
    vitaminD: Optional[float] = Field(
        default=None, description="Vitamin D in micrograms"
    )
    vitaminE: Optional[float] = Field(
        default=None, description="Vitamin E in milligrams"
    )
    vitaminPP: Optional[float] = Field(
        default=None, description="Vitamin PP in milligrams"
    )
    vitaminK: Optional[float] = Field(
        default=None, description="Vitamin K in micrograms"
    )

    # Minerals
    zinc: Optional[float] = Field(default=None, description="Zinc in milligrams")
    phosphorus: Optional[float] = Field(
        default=None, description="Phosphorus in milligrams"
    )
    iodine: Optional[float] = Field(default=None, description="Iodine in micrograms")
    magnesium: Optional[float] = Field(
        default=None, description="Magnesium in milligrams"
    )
    copper: Optional[float] = Field(default=None, description="Copper in milligrams")
    potassium: Optional[float] = Field(
        default=None, description="Potassium in milligrams"
    )
    selenium: Optional[float] = Field(
        default=None, description="Selenium in micrograms"
    )
    sodium: Optional[float] = Field(default=None, description="Sodium in milligrams")
    calcium: Optional[float] = Field(default=None, description="Calcium in milligrams")
    iron: Optional[float] = Field(default=None, description="Iron in milligrams")

    measures: List[NutritionMeasure] = Field(description="List of measurement units")


def convert_menu_meal_to_nutrition_product(
    menu_meal: DeliveryMenuMeal, brand: str
) -> NutritionProduct:
    """Convert a DeliveryMenuMeal from Dietly API to a NutritionProduct for Fitatu API.

    Args:
        menu_meal: Menu meal data from Dietly API
        brand: Brand name to assign to the product

    Returns:
        NutritionProduct instance ready for Fitatu API
    """
    nutrition = menu_meal.nutrition

    # Create measures from weight if available
    measures = []
    if hasattr(nutrition, "weight") and nutrition.weight:
        measures.append(
            NutritionMeasure(
                measureKey="PACKAGE", measureUnit="g", weight=str(nutrition.weight)
            )
        )

    return NutritionProduct(
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
        measures=measures,
    )
