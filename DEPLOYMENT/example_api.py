from datetime import datetime
from typing import Union, Optional, Annotated
from pydantic import BaseModel, PositiveInt
from fastapi import FastAPI, Query, Path, Body
from enum import Enum


class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"


class Item(BaseModel):
    name: str
    description: Union[str, None] = None
    price: float
    tax: Union[float, None] = None


class User(BaseModel):
    username: str
    full_name: Union[str, None] = None


app = FastAPI()

fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]


# @app.get('/')
# async def root():
#     return {'message': "Hello World"}


@app.get("/items/")
async def read_items(
        q: Annotated[
            Union[str, None],
            Query(
                alias="item-query",
                title="Query string",
                description="Query string for the items to search in the database that have a good match",
                min_length=3,
                max_length=50,
                deprecated=False,
            ),
        ] = None,
):
    results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if q:
        results.update({"q": q})
    return results


@app.post("/items/")
async def create_item(item: Item):
    if item.tax:
        price_with_tax = item.price + item.tax
        name_longer = item.name + '_' + item.description
        result = {**item.dict(), "price_with_tax": price_with_tax, 'name_desc': name_longer}
    else:
        result = item.dict()
    return result


@app.get("/items/{item_id}")
async def read_items(
        item_id: Annotated[int, Path(title="The ID of the item to get", ge=1, le=1000)],
        q: Annotated[Union[str, None], Query(alias="item-query")] = None,
        item: Union[float, None] = None
):
    results = {"item_id": item_id}
    if q:
        results.update({"q": q})
    return results


@app.put("/items/{item_id}")
async def update_item(
        item_id: int, item: Annotated[Item, Body(embed=True)], user: User, importance: Annotated[int, Body()]
):
    results = {"item_id": item_id, "item": item, "user": user, "importance": importance}
    return results


@app.get("/users/{user_id}/items/{item_id}")
async def read_user_item(user_id: int,
                         item_id: str,
                         q: Union[str, None] = None,
                         short: bool = False):
    item = {"item_id": item_id, "owner_id": user_id}
    if q:
        item.update({"q": q})
    if not short:
        item.update(
            {"description": "This is an amazing item that has a long description"}
        )
    return item


@app.get("/users/{user_id}")
async def read_user(user_id: str):
    return {"user_id": user_id}


@app.get("/models/{model_name}")
async def get_model(model_name: ModelName):
    if model_name is ModelName.alexnet:
        return {"model_name": model_name, "message": "Deep Learning FTW!"}

    if model_name.value == "lenet":
        return {"model_name": model_name, "message": "LeCNN all the images"}

    return {"model_name": model_name, "message": "Have some residuals"}
