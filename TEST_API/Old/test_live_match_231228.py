import os.path
from live_data_format_adjust import Engine
from live_score_model_for_api import LiveScore_Model
import pickle
import pandas as pd
import math
from tqdm import tqdm
from pprint import pprint
import json

# ------------- INITIALIZATION ---------------------
match_id_ = 77854937 #77926259 #77623787 #77592032
position = 0
event_code_ids = []

# load model
pickle_file_path = '../model/Span_Primera_Ferderacion/ada_live_model.sav'
with open(pickle_file_path, 'rb') as file:
    rf_model = pickle.load(file)
# Create Live model
live_model = LiveScore_Model(model=rf_model)


# ------------- CALL API FOR LIVE MATCH -------------
json_file_path = r'C:\Users\user2\PycharmProjects\Livescore_model\TEST_API\rb_code_upd.json'
# Open the file and load the JSON data
with open(json_file_path, 'r') as json_file:
    rb_code = json.load(json_file)

match = Engine(match_id=match_id_,
               event_code_ids=event_code_ids,
               selected_ids=rb_code,
               event_position=position)

js_adm, final_output = match.get_AB_timer_metadata(isFT=True, is_live=True)


# TEST LIVE MATCH
is_running = match.is_running
# while is_running:
for i in range(10):
    log_api = match.get_logs_for_current_match(isFT=True)
    js_adm, final_output = match.get_AB_timer_metadata(isFT=True,
                                                       is_live=True)

    if log_api is not None:
        print('\n\n Live Timer:')
        pprint(log_api['Timer'])
        try:
            print('\n\n In game Timer:')
            pprint(log_api['ingame_Timer'])
            ability = live_model.predict_expected_ability(input_api_json=log_api)

        except KeyError:
            print(log_api)
            break
        finally:
            is_running = match.is_running
    else:
        print(f'Game has been not started yet, It remains around {final_output["Timer"]["LiveTimer"]} seconds before staring games')


# ------------- SAVE LOG FILE FOR LIVE MATCH -------------
#match.save_json(is_live_match=False, file_directory='api_folder')
# pprint(match.full_rb_events)
file_name = match.full_path[0]
full_ability_df = pd.DataFrame(live_model.ability_match)
full_match_ab_df = pd.DataFrame(data=live_model.full_match_sep)
full_match_atk_rd = pd.concat(live_model.full_atk_rd_match)

# feat
feat = ['period', 'second', 'field', 'has_event', 'update', 'home_p_in/de', 'away_p_in/de',
        'home_perf_coef', 'away_perf_coef', 'home_ability', 'away_ability',
        'home_exp_ability', 'away_exp_ability']

# Save a file CSV
final_filename = f"ab_{os.path.split(file_name)[-1].split('.')[0]}.csv"
final_filename = os.path.join('api_folder', str(match_id_), final_filename)
full_ability_df[feat].to_csv(final_filename, index=False)

print(f"Export file: {final_filename} completely")
print(full_ability_df.shape)
print(full_match_ab_df.shape)