from fastapi import FastAPI, Depends
from pydantic import BaseModel, PositiveInt
from typing import Union, Optional, Annotated

class PARAMS(BaseModel):
    match_id: Annotated[Union[int, None], Query(alias="match id", description="Please provide ibc match id", )]
    dst_pth: str

# Example class - Predictor
# Example class
class Predictor:
    def __init__(self, match_id: str):
        # Initialization logic here
        self.match_id = match_id

    def predict(self, input_data: str):
        # Your prediction logic here
        result = f"Predicted result for {input_data} in match {self.match_id}"
        return result

    def get_event_data(self):
        # Your logic to get event data
        event_data = f"Event data for match {self.match_id}"
        return event_data


# Example class - Collector
class Collector:
    def __init__(self, source: str):
        self.source = source

    def collect_data(self):
        return f"Collected data from source: {self.source}"


# FastAPI application
app = FastAPI()


# Dependency to create an instance of Predictor
def get_predictor(match_id: str):
    return Predictor(match_id)


# Dependency to create an instance of Collector
def get_collector(source: str):
    return Collector(source)


# API endpoint using both dependencies
@app.post("/process_data/{match_id}/{source}")
def process_data(
        match_id: str,
        source: str,
        input_data: str,
        predictor: Predictor = Depends(get_predictor),
        collector: Collector = Depends(get_collector),
):
    prediction_result = predictor.predict(input_data)
    collected_data = collector.collect_data()

    return {
        "prediction_result": prediction_result,
        "collected_data": collected_data,
    }


# Another API endpoint using the same instance
@app.get("/get_event_data/{match_id}")
def get_event_data(
        match_id: str,
        predictor: Predictor = Depends(get_predictor),
):
    event_data = predictor.get_event_data()
    return {"event_data": event_data}
