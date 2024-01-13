import json, pickle
import os.path
import pandas as pd
from typing import Union, Optional, Annotated
from pydantic import BaseModel, PositiveInt
from fastapi import FastAPI, Query, Path, Body, Depends
from enum import Enum
from TEST_API.live_data_api_engine import Engine
from TEST_API.live_score_model_for_api import LiveScore_Model
from tqdm import tqdm
import time

# DATA OF MATCH
# K.O Time: 08:30 PM
# League: EGYPT SECOND DIVISION A
# Match: Petrojet -vs- Haras El Hodood
# Match ID: 78995950
# TV/IPTV:
# Provider: RB2

# K.O Time: 02:30 PM
# League: VIETNAM CHAMPIONSHIP U19 QUALIFIERS
# Match: Becamex Binh Duong U19 (N) -vs- Ho Chi Minh City FC U19
# Match ID: 79066664
# TV/IPTV:
# Provider: RB2
# ------------- INITIALIZATION ---------------------

match_id_ = 78995950  # 78534882  # 78378471 #77422531 #78329100 #78327701 #78088596 #77854937 #77926259 #77623787 #77592032
position = 0
# event_code_ids = []
dest_path = r'D:\TRI_LE\GOAL_LIVE_PREDATOR\TEST_API\api_folder'
rb_path = r'D:\TRI_LE\GOAL_LIVE_PREDATOR\TEST_API\official_rb_code.json'


# -----------------------------------------------------------
# Dependency to create an instance of Predictor
def get_predictor(pickle_path: str):
    # load model
    with open(pickle_path, 'rb') as file:
        rf_model = pickle.load(file)

    # Create Live model
    return LiveScore_Model(model=rf_model)


# Dependency to create an instance of Collector
def get_collector(match_id: int,
                  rb_code_file: str = 'official_rb_code.json',
                  event_position: int = 0,
                  destination_dir: str = 'api_folder',
                  root_dir: str = r"D:\TRI_LE\GOAL_LIVE_PREDATOR\TEST_API"
                  ):
    # ------------- FUNCTION ---------------------
    def create_directory(dir_path):
        # Check if the directory path exists
        if not os.path.exists(dir_path):
            try:
                # Create the directory if it doesn't exist
                os.makedirs(dir_path)
                print(f"Directory '{dir_path}' created successfully.")
            except OSError as e:
                print(f"Error creating directory '{dir_path}': {e}")
        else:
            print(f"Directory '{dir_path}' already exists. No need to create more directory")

    # ------------- CALL API FOR LIVE MATCH -------------
    rb_code_path_ = os.path.join(root_dir, rb_code_file)
    destination_dir_ = os.path.join(root_dir, destination_dir)

    # Check location is existed ?
    create_directory(rb_code_path_)
    create_directory(destination_dir_)

    # Open the file and load the JSON data
    with open(rb_code_path_, 'r') as json_file:
        rb_code = json.load(json_file)

    return Engine(match_id=match_id,
                  event_code_ids=[],
                  selected_ids=rb_code,
                  event_position=event_position,
                  destination_dir=destination_dir_)


# =========== INITIALIZATION ================
app = FastAPI(debug=True)


# 1st API: Getting match abilities and metadata from match ID
# /api/v1/match_info/{match_id}?rb_code_file=...&event_position=...&destination_dir=...&root_dir=...
@app.post("/api/v1/match_info/{match_id}")
def response_meta_data(
        match_id: str,
        collector: Engine = Depends(get_collector),
):
    # get metadata and abilities
    output = collector.get_AB_timer_metadata(isFT=True, is_live=True)

    return output

# 2nd API: Fetching RB event and transform to event counter. Then predicting to ab for PAST MATCH
# /api/v1/predict_past_match/{match_id}

@app.get('/api/v1/predict_past_match/{match_id}')
async def get_event_counter(
        match_id: str,
        predictor: LiveScore_Model = Depends(get_predictor),
        collector: Engine = Depends(get_collector)
):
    full_log_apis = collector.get_logs_for_past_match(isFT=True)
    collector.save_json(is_live_match=False)
    file_name = collector.full_path[0]

    # ------------- USE LGP TO PREDICT ABILITY -------------
    # Create atk round list and ability of full match list
    for dict_sec in tqdm(full_log_apis, desc="Starting to execute the api...."):
        ability = predictor.predict_expected_ability(input_api_json=dict_sec)

    full_ability_df = pd.DataFrame(predictor.ability_match)

    # feat
    feat = ['period', 'second', 'field', 'has_event', 'update', 'home_p_in/de', 'away_p_in/de',
            'home_perf_coef', 'away_perf_coef', 'home_ability', 'away_ability',
            'home_exp_ability', 'away_exp_ability']

    # Save a file CSV
    final_filename = f"ab_{os.path.split(file_name)[-1].split('.')[0]}.csv"
    final_filename = os.path.join(dest_path, str(match_id_), final_filename)
    full_ability_df[feat].to_csv(final_filename, index=False)

    print(f"Export file: {final_filename} completely")

    return {collector.match_id: {'past_match_data_dir': file_name}}


# 3RD API: Fetching RB event and transform to counter of RB event
# /api/v1/get_event_counter/{match_id}
@app.get('/api/v1/get_event_counter/{match_id}')
async def transform_to_event_counter(
        match_id: str,
        collector: Engine = Depends(get_collector)
):
    # TEST LIVE MATCH
    #is_running = collector.is_running

    final_output = collector.get_AB_timer_metadata(isFT=True, is_live=True)
    break_time = 0
    # for i in range(10):

    try:
        log_api = collector.get_logs_for_current_match()
        period = log_api['ingame_Timer']['in_game_period']
        # js_adm, final_output = match.get_AB_timer_metadata(isFT=True,is_live=True)
        time.sleep(0.3)
    except ConnectionError as e:
        print(f">>>>>>>>>> THERE IS ERROR DURING FETCHING DATA: {e}")
        #is_running = False
        raise e
    else:
        return log_api