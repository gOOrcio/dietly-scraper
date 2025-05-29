from typing import List, Optional
from pydantic import BaseModel, RootModel


class ActiveOrder(BaseModel):
    companyName: str
    companyFullName: str
    companyImageUrl: str
    orderId: int


class Payment(BaseModel):
    paid: float
    cost: float
    accepted: str


class DeliveryMeal(BaseModel):
    deliveryMealId: int
    amount: int
    dietCaloriesMealId: int
    addedByUser: bool
    deleted: bool


class Delivery(BaseModel):
    deliveryId: int
    date: str
    hourPreference: str
    dietCaloriesId: int
    tierId: Optional[int]
    addressId: int
    pickupPointId: Optional[int]
    deliverySpot: str
    deleted: bool
    deliveryMeals: List[DeliveryMeal]
    sideOrders: List[dict] = []


class Diet(BaseModel):
    dietName: str
    dietOptionName: str
    tierName: Optional[str]
    calories: int
    dietImage: str
    menuConfiguration: bool
    menuConfigurationWithTiers: bool


class NearestDelivery(BaseModel):
    nearestDeliveryDate: str
    deliveryDates: List[str]
    addressId: int
    mealAmount: int


class OrderDetails(BaseModel):
    orderId: int
    dateFrom: str
    dateTo: str
    source: str
    status: str
    discountTotal: float
    discountPercentage: float
    testOrder: bool
    clientId: int
    shoppingCartId: int
    payment: Payment
    feedback: Optional[str]
    deliveries: List[Delivery]
    diet: Diet
    nearestDelivery: NearestDelivery


class ActiveOrdersResponse(RootModel[List[ActiveOrder]]):
    root: List[ActiveOrder]
    
    def __iter__(self):
        return iter(self.root)
    
    def __getitem__(self, item):
        return self.root[item]
    
    def __len__(self):
        return len(self.root) 