from typing import List, Optional

from pydantic import BaseModel


class Nutrition(BaseModel):
    weight: float
    calories: float
    fat: float
    protein: float
    carbohydrate: float
    dietaryFiber: float
    sugar: float
    salt: float
    saturatedFattyAcids: float
    caloriesText: str


class AllergenWithExcluded(BaseModel):
    dietaryExclusionId: int
    companyAllergenName: str
    dietlyAllergenName: str
    excluded: bool


class IngredientExclusion(BaseModel):
    dietaryExclusionId: int
    name: str
    chosen: bool


class Ingredient(BaseModel):
    name: str
    major: bool
    exclusion: List[IngredientExclusion]


class DeliveryMenuMeal(BaseModel):
    deliveryMealId: int
    amount: int
    mealName: str
    mealPriority: int
    menuMealId: int
    menuMealName: str
    thermo: Optional[str]
    dietCaloriesMealId: int
    dietCaloriesId: int
    nutrition: Nutrition
    allergens: List[str]
    allergensWithExcluded: List[AllergenWithExcluded]
    ingredients: List[Ingredient]
    review: Optional[str]
    addedByUser: bool
    switchable: bool
    mealAddingSource: bool
    deliveryMealSeen: str
    reviewSummary: Optional[str]
    menuMealImageUrl: Optional[str]
    dietTag: str


class MenuResponse(BaseModel):
    menuVisible: str
    showNutrition: bool
    showIngredients: bool
    deliveryMenuMeal: List[DeliveryMenuMeal]
    possibleSideOrders: List
