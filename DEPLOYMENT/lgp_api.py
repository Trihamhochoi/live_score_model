import json, pickle
from typing import Union, Optional, Annotated
from pydantic import BaseModel, PositiveInt
from fastapi import FastAPI, Query, Path, Body
from enum import Enum
from TEST_API.live_data_api_engine import Engine
from live_score_model_for_api import LiveScore_Model

# ------------- INITIALIZATION ---------------------

match_id_ = 77506141  # 78534882  # 78378471 #77422531 #78329100 #78327701 #78088596 #77854937 #77926259 #77623787 #77592032
position = 0
event_code_ids = []
dest_path = r'C:\Users\user2\PycharmProjects\Livescore_model\TEST_API\api_folder'

# load model
pickle_file_path = r'C:\Users\user2\PycharmProjects\Livescore_model\model\Germany_3rd_liga\ada_live_model.sav'
with open(pickle_file_path, 'rb') as file:
    rf_model = pickle.load(file)
# Create Live model
live_model = LiveScore_Model(model=rf_model)

# ------------- CALL API FOR LIVE MATCH -------------
json_file_path = r'C:\Users\user2\PycharmProjects\Livescore_model\TEST_API\official_rb_code.json'
# Open the file and load the JSON data
with open(json_file_path, 'r') as json_file:
    rb_code = json.load(json_file)

# engine = Engine(match_id=match_id_,
#                 event_code_ids=event_code_ids,
#                 selected_ids=rb_code,
#                 event_position=position,
#                 destination_dir=dest_path)

app = FastAPI(debug=True)


# PARAMS
class PARAMS(BaseModel):
    match_id: Annotated[Union[int, None], Query(alias="match id", description="Please provide ibc match id", )]
    dst_pth: str


@app.post("/api/v1/match_info/")
def response_meta_data(param: PARAMS):
    eng = Engine(match_id=param.match_id,
                 event_code_ids=[],
                 selected_ids=rb_code,
                 event_position=0,
                 destination_dir=param.dst_pth)

    final_output = eng.get_AB_timer_metadata(isFT=True, is_live=True)

    return final_output
