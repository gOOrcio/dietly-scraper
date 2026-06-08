"""Pydantic models for the Dietly order/details API.

Validation philosophy: Dietly's responses are *input* we don't control, and
they routinely return ``null`` for fields that are optional in their UI
(e.g. ``hourPreference``). We only ever consume a tiny slice of this payload —
to locate today's delivery we read ``OrderDetails.deliveries[].deliveryId``,
``.date`` and ``.deleted``; the menu we actually post to Fitatu comes from a
*separate* endpoint (see ``menu_response_model``). So we validate strictly only
the handful of fields the code depends on, and treat everything else as
best-effort metadata: optional, with defaults, so a stray ``null`` from Dietly
can never drop an otherwise-valid order. Tightening a field here means "our code
now relies on it"; until then, keep it lenient.
"""

from typing import List, Optional

from pydantic import BaseModel, RootModel


class ActiveOrder(BaseModel):
    # companyName / companyFullName / orderId are consumed in dietly_client to
    # build headers and look up order details — keep them strict.
    companyName: str
    companyFullName: str
    orderId: int
    companyImageUrl: Optional[str] = None


class Payment(BaseModel):
    # Not consumed — metadata only.
    paid: Optional[float] = None
    cost: Optional[float] = None
    accepted: Optional[str] = None


class DeliveryMeal(BaseModel):
    # Not consumed — metadata only.
    deliveryMealId: Optional[int] = None
    amount: Optional[int] = None
    dietCaloriesMealId: Optional[int] = None
    addedByUser: Optional[bool] = None
    deleted: Optional[bool] = None


class Delivery(BaseModel):
    # Consumed in find_delivery_for_date — keep these three strict.
    deliveryId: int
    date: str
    deleted: bool
    # Everything below is metadata Dietly may return as null; do not validate.
    hourPreference: Optional[str] = None
    dietCaloriesId: Optional[int] = None
    tierId: Optional[int] = None
    addressId: Optional[int] = None
    pickupPointId: Optional[int] = None
    deliverySpot: Optional[str] = None
    deliveryMeals: List[DeliveryMeal] = []
    sideOrders: List[dict] = []


class Diet(BaseModel):
    # Not consumed — metadata only.
    dietName: Optional[str] = None
    dietOptionName: Optional[str] = None
    tierName: Optional[str] = None
    calories: Optional[int] = None
    dietImage: Optional[str] = None
    menuConfiguration: Optional[bool] = None
    menuConfigurationWithTiers: Optional[bool] = None


class NearestDelivery(BaseModel):
    # Not consumed — metadata only.
    nearestDeliveryDate: Optional[str] = None
    deliveryDates: List[str] = []
    addressId: Optional[int] = None
    mealAmount: Optional[int] = None


class OrderDetails(BaseModel):
    # Only `deliveries` is consumed (to find today's delivery id). Default it to
    # [] so an order with no deliveries surfaces as "no active plan" rather than
    # a validation crash. Everything else is optional metadata.
    deliveries: List[Delivery] = []
    orderId: Optional[int] = None
    dateFrom: Optional[str] = None
    dateTo: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    discountTotal: Optional[float] = None
    discountPercentage: Optional[float] = None
    testOrder: Optional[bool] = None
    clientId: Optional[int] = None
    shoppingCartId: Optional[int] = None
    payment: Optional[Payment] = None
    feedback: Optional[str] = None
    diet: Optional[Diet] = None
    nearestDelivery: Optional[NearestDelivery] = None


class ActiveOrdersResponse(RootModel[List[ActiveOrder]]):
    root: List[ActiveOrder]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]

    def __len__(self):
        return len(self.root)
