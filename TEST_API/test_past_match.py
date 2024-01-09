# import sys
# sys.path.append(r'C:\Users\user2\PycharmProjects\Livescore_model')
import os
from live_data_api_engine import Engine
from live_score_model_for_api import LiveScore_Model
import pickle
import pandas as pd
import math
from tqdm import tqdm
import json


# ------------- INITIALIZATION ---------------------
# TestCase
# K.O Time: 09:30 PM
# League: SOUTH AFRICA PREMIERSHIP
# Match: Cape Town City FC -vs- Mamelodi Sundowns
# Match ID: 77433048
# TV/IPTV:
# Provider: RB2

match_id_ = 78534882 #77433048  # 78041432  # 77994064 #78041654 #78041657 #78041654 #77304851  # 77926259  # 77623787 #77592032
event_code_ids = []
position = 0
dest_path = r'C:\Users\user2\PycharmProjects\Livescore_model\TEST_API\api_folder'

# load model
pickle_file_path = r'C:\Users\user2\PycharmProjects\Livescore_model\model\Span_Primera_Ferderacion\ada_live_model.sav'
with open(pickle_file_path, 'rb') as file:
    rf_model = pickle.load(file)

# Create Live model
live_model = LiveScore_Model(model=rf_model)

# ------------- CALL API FOR PAST MATCH -------------
json_file_path = r'C:\Users\user2\PycharmProjects\Livescore_model\TEST_API\official_rb_code.json'
# Open the file and load the JSON data
with open(json_file_path, 'r') as json_file:
    rb_code = json.load(json_file)

match = Engine(match_id=match_id_,
               event_code_ids=event_code_ids,
               selected_ids=rb_code,
               event_position=position,
               destination_dir=dest_path)

js_adm, final_output = match.get_AB_timer_metadata(isFT=True,
                                                   is_live=False)

# TEST PAST MATCH
full_log_apis = match.get_logs_for_past_match(isFT=True)
match.save_json(is_live_match=False)
file_name = match.full_path[0]

# ------------- USE LGP TO PREDICT ABILITY -------------
# Create atk round list and ability of full match list
current_atk_round = None
full_ability = None
for dict_sec in tqdm(full_log_apis, desc="Starting to execute the api...."):
    ability = live_model.predict_expected_ability(input_api_json=dict_sec)
                                                  # attacking_round_list=current_atk_round,
                                                  # ability_fullmatch_list=full_ability


    # full_ability = ability_full_match
    # current_atk_round = atk_round

full_ability_df = pd.DataFrame(live_model.ability_match)
full_match_ab_df = pd.DataFrame(data=live_model.full_match_sep)
full_match_atk_rd = pd.concat(live_model.full_atk_rd_match)

# feat
feat = ['period', 'second', 'field', 'has_event', 'update', 'home_p_in/de', 'away_p_in/de',
        'home_perf_coef', 'away_perf_coef', 'home_ability', 'away_ability',
        'home_exp_ability', 'away_exp_ability']

# Save a file CSV
final_filename = f"ab_{os.path.split(file_name)[-1].split('.')[0]}.csv"
final_filename = os.path.join(dest_path, str(match_id_), final_filename)
full_ability_df[feat].to_csv(final_filename, index=False)

print(f"Export file: {final_filename} completely")
print(full_ability_df.shape)
print(full_match_ab_df.shape)
