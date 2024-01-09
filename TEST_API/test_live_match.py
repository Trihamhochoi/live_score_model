import os.path
from live_data_api_engine import Engine
from live_score_model_for_api import LiveScore_Model
import pickle
import pandas as pd
import math
from tqdm import tqdm
from pprint import pprint
import json
import numpy as np
import time
import logging
# K.O Time: 09:00 PM
# League: TUNISIAN LEAGUE 2
# Match: CS Hammam Lif -vs- ES Hammam Sousse
# Match ID: 78329100
# TV/IPTV:
# Provider: RB2

# K.O Time: 02:00 PM
# League: AUSTRALIA WOMEN A LEAGUE
# Match: Sydney FC (W) -vs- Wellington Phoenix FC (W)
# Match ID: 77422531
# TV/IPTV: IPTV/Bet365/Bet365/TNT Sport 4 [876]/Glive-750
# Provider: TV/RB2tv/GLive750

# K.O Time: 04:00 PM
# League: ISRAEL LIGA BET
# Match: Beitar Ramat Gan FC -vs- Hapoel Kiryat Ono FC
# Match ID: 78378471
# TV/IPTV:
# Provider: RB2

# K.O Time: 08:10 PM
# League: SAUDI 1ST DIVISION
# Match: Al Qaisumah -vs- Al Taraji
# Match ID: 78534882
# TV/IPTV: iptv/Not Set
# Provider: TV/RB2tv

# K.O Time: 06:30 PM
# League: SPAIN PRIMERA FEDERACION
# Match: Recreativo Granada -vs- UD Melilla
# Match ID: 77506141
# TV/IPTV:
# Provider: RB2

# ------------- INITIALIZATION ---------------------

match_id_ = 77506141 #78534882  # 78378471 #77422531 #78329100 #78327701 #78088596 #77854937 #77926259 #77623787 #77592032
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

match = Engine(match_id=match_id_,
               event_code_ids=event_code_ids,
               selected_ids=rb_code,
               event_position=position,
               destination_dir=dest_path)

# TEST LIVE MATCH
is_running = match.is_running

js_adm, final_output = match.get_AB_timer_metadata(isFT=True, is_live=True)

# for i in range(10):
while is_running:

    log_api = match.get_logs_for_current_match()
    period = log_api['ingame_Timer']['in_game_period']
    # js_adm, final_output = match.get_AB_timer_metadata(isFT=True,is_live=True)
    # time.sleep(0.2)

    if period in [0, 11, 22]:
        print(f'--- It remains {final_output["Timer"]["min"]}'
              f' min {final_output["Timer"]["sec"]} secs before staring games\n\n')

    elif period in [1, 2]:
        # # ---- EXAMINE WHICH THE EVENT CODE IS COUNTED -------
        # keys = list(log_api['Event'].keys())
        # diff_event_counter = np.array(list(log_api['Event'].values())) - np.array(list(log_api['LastEvent'].values()))
        # timer = {key: log_api['ingame_Timer'][key] for key in ['in_game_period', 'min', 'sec']}
        # event_change = {keys[i]: v for i, v in enumerate(diff_event_counter) if v > 0}
        # final = timer.copy()
        # final.update(event_change)
        # if len(event_change) > 0:
        #     print(f'--- There is update event: {final}')
        try:
            # Apply ability for the match
            ability = live_model.predict_expected_ability(input_api_json=log_api)
        except KeyError as e:
            print(e)
            print(log_api)

        finally:
            is_running = match.is_running

# ------------- SAVE LOG FILE FOR LIVE MATCH -------------
try:
    # pprint(match.full_rb_events)
    match.save_json(is_live_match=True)
    file_name = match.full_path[0]
    full_ability_df = pd.DataFrame(live_model.ability_match)
    full_match_ab_df = pd.DataFrame(data=live_model.full_match_sep)
    # full_match_atk_rd = pd.concat(live_model.full_atk_rd_match)
except Exception as e:
    raise e
else:
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
