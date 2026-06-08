"""Pydantic models for the Dietly delivery-menu API.

Same validation philosophy as ``dietly_order_models``: Dietly's menu payload is
input we don't control and routinely carries ``null`` in fields we never read
(and sometimes in ones we do). We validate strictly only what we actually post
to Fitatu and treat everything else as best-effort metadata.

The one field we genuinely need per meal is ``nutrition`` (the macros we push to
Fitatu). Some company plans return ``nutrition: null`` for every meal (e.g. when
the plan hides nutrition), which previously killed the whole user's sync with a
``model_type`` error. So ``nutrition`` is now optional; meals without it are
skipped downstream (see ``process_menu_meals``) rather than crashing the run.
Within a *present* ``Nutrition`` object we keep the core macros Fitatu requires
(weight/calories/fat/protein/carbohydrate) strict and let the rest be null.
"""

from typing import List, Optional

from pydantic import BaseModel


class Nutrition(BaseModel):
    # Core macros posted to Fitatu as required values — keep strict.
    weight: float
    calories: float
    fat: float
    protein: float
    carbohydrate: float
    # Posted to Fitatu's optional fields; Dietly may null any of these.
    dietaryFiber: Optional[float] = None
    sugar: Optional[float] = None
    salt: Optional[float] = None
    saturatedFattyAcids: Optional[float] = None
    # Not consumed.
    caloriesText: Optional[str] = None


class AllergenWithExcluded(BaseModel):
    # Not consumed — metadata only.
    dietaryExclusionId: Optional[int] = None
    companyAllergenName: Optional[str] = None
    dietlyAllergenName: Optional[str] = None
    excluded: Optional[bool] = None


class IngredientExclusion(BaseModel):
    # Not consumed — metadata only.
    dietaryExclusionId: Optional[int] = None
    name: Optional[str] = None
    chosen: Optional[bool] = None


class Ingredient(BaseModel):
    # Not consumed — metadata only.
    name: Optional[str] = None
    major: Optional[bool] = None
    exclusion: List[IngredientExclusion] = []


class DeliveryMenuMeal(BaseModel):
    # Consumed in process_menu_meals / the Fitatu converter — keep strict.
    mealName: str
    menuMealName: str
    # Optional: code already skips meals whose deliveryMealId is None.
    deliveryMealId: Optional[int] = None
    # Optional: null for plans that don't expose nutrition; such meals are
    # skipped rather than failing the whole menu.
    nutrition: Optional[Nutrition] = None
    # Everything below is metadata we never read; tolerate any null.
    amount: Optional[int] = None
    mealPriority: Optional[int] = None
    menuMealId: Optional[int] = None
    thermo: Optional[str] = None
    dietCaloriesMealId: Optional[int] = None
    dietCaloriesId: Optional[int] = None
    allergens: List[str] = []
    allergensWithExcluded: List[AllergenWithExcluded] = []
    ingredients: List[Ingredient] = []
    review: Optional[str] = None
    addedByUser: Optional[bool] = None
    switchable: Optional[bool] = None
    mealAddingSource: Optional[bool] = None
    deliveryMealSeen: Optional[str] = None
    reviewSummary: Optional[str] = None
    menuMealImageUrl: Optional[str] = None
    dietTag: Optional[str] = None


class MenuResponse(BaseModel):
    # Only deliveryMenuMeal is consumed; default to [] so an empty menu is
    # handled as "no meals" rather than a validation error.
    deliveryMenuMeal: List[DeliveryMenuMeal] = []
    menuVisible: Optional[str] = None
    showNutrition: Optional[bool] = None
    showIngredients: Optional[bool] = None
    possibleSideOrders: List = []
