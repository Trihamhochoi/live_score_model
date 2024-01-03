import pandas as pd
import json
import numpy as np
import math
import warnings
import re
import os
from pprint import pprint
import pathlib
from tqdm import tqdm

pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', 50)
warnings.filterwarnings("ignore")


class Preprocess_log_data:
    def __init__(self, log_url):
        self.match_api = None
        self.log_url = log_url


    def convert_log_match(self):
        log_cols = [
            'cm_league_id', 'cm_period', 'cm_timer', 'match_id',
            'cm_home_id', 'cm_home_score', 'cm_home_ability',  # HOME
            'cm_home_safe', 'cm_home_throwin',  # Condition to start attacking round
            'cm_home_woodwork', 'cm_home_shot_on_target',
            'cm_home_attack', 'cm_home_danger_attack', 'cm_home_danger', 'cm_home_corner', 'cm_home_freekick',
            'cm_home_danger_freekick',
            'cm_away_id', 'cm_away_score', 'cm_away_ability',  # AWAY
            'cm_away_safe', 'cm_away_throwin',
            'cm_away_woodwork', 'cm_away_shot_on_target',
            'cm_away_attack', 'cm_away_danger_attack', 'cm_away_danger', 'cm_away_corner', 'cm_away_freekick',
            'cm_away_danger_freekick',
        ]
        log_match = pd.read_csv(self.log_url, usecols=log_cols)

        # get dict of ability of 2 teams
        full_ability = []
        for row in log_match[['cm_home_ability', 'cm_away_ability']].itertuples(index=False, name=None):
            ability_dict = {"Home": row[0],
                            "Away": row[1]}
            is_na = any([math.isnan(v) for v in ability_dict.values()])
            if not is_na:
                full_ability.append(ability_dict)

        # Get dict of metadata of a match
        metadata = []
        for row in log_match[['cm_league_id', 'match_id', 'cm_home_id', 'cm_away_id']].itertuples(index=False,name=None):
            _dict = {"MatchTime": 90,
                     "LeagueId": row[0],
                     'MatchID': row[1],
                     "HomeTeamId": row[2],
                     "AwayTeamId": row[3]}
            is_na = any([math.isnan(v) for v in _dict.values()])
            if not is_na:
                metadata.append(_dict)


        # Get timer of match
        full_timer = []
        for row in log_match[['cm_period', 'cm_timer']].itertuples(index=False, name=None):
            _dict = {"LiveTimer": row[1],
                     "LivePeriod": row[0]}
            is_na = any([math.isnan(v) for v in _dict.values()])
            if not is_na:
                full_timer.append(_dict)

        # MAPPING LOG FILE COLUMNS VS API COLUMNS
        log_event_cols = ['cm_home_score','cm_away_score',
                          'cm_home_corner','cm_away_corner',
                          'cm_home_freekick','cm_away_freekick',
                          'cm_home_danger_freekick', 'cm_away_danger_freekick',
                          'cm_home_shot_on_target', 'cm_away_shot_on_target',
                          'cm_home_woodwork','cm_away_woodwork',
                          'cm_home_throwin','cm_away_throwin',
                          'cm_home_attack', 'cm_away_attack',
                          'cm_home_danger_attack','cm_away_danger_attack',
                          'cm_home_danger', 'cm_away_danger',
                          'cm_home_safe','cm_away_safe']

        api_event_key_name = ['Score1', 'Score2', # GOAL1, GOAL2
                              'CR1', 'CR2',
                              'FK1', 'FK2',
                              'DFK1', 'DFK2',
                              'SONT1', 'SONT2', # SHG1, SHG2
                              'SWW1','SWW2', # SHW1, SHW2
                              'TI1','TI2',
                              'ATT1', 'ATT2', # AT1, AT2
                              'DATT1','DATT2', # DAT1, DAT2
                              'DAN1', 'DAN2',
                              'SAFE1','SAFE2']

        event_key_mapping = {old: new for old, new in zip(log_event_cols, api_event_key_name)}

        # Format the event data
        event_dict = log_match[log_event_cols].to_dict(orient='records')

        # Update the key name
        full_events = []
        for d in event_dict:
            new_dict = {event_key_mapping.get(k): v for k, v in d.items()}
            is_na = any([math.isnan(v) for v in new_dict.values()])
            if not is_na:
                full_events.append(new_dict)

        # CREATE API
        #print(len(full_ability),len(metadata), len(full_timer), len(full_events))
        match_api = []
        for i, (a, m, t, e) in enumerate(zip(full_ability, metadata, full_timer, full_events)):
            if i == 0:
                first_last_event = {k: 0 for k, v in full_events[i].items()}
                comprehensive_dict = {'Ability': a, 'Match': m, 'Timer': t, 'Event': e, 'LastEvent': first_last_event}
            else:
                comprehensive_dict = {'Ability': a, 'Match': m, 'Timer': t, 'Event': e, 'LastEvent': full_events[i - 1]}
            match_api.append(comprehensive_dict)

        self.match_api = match_api
        return self.match_api

    def save_json(self,file_directory='json/'):

        # Check directory
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
                print(f"Directory '{dir_path}' already exists. Starting to execute log file and add into the corresponding directory.")

        # Check directory input
        create_directory(dir_path=file_directory)
        # Save into json file
        # Specify the file name where you want to save the JSON data
        name = pathlib.Path(self.log_url).stem
        json_file_name = f'{name}.json'
        self.full_path = os.path.join(file_directory,json_file_name)

        # Save the dictionary to a JSON file
        with open(self.full_path, 'w') as json_file:
            json.dump(self.match_api, json_file, indent=4)
        print(f'Dictionary saved to {self.full_path}')


if __name__ == '__main__':
    # log_url = 'log_data/20231003_uat_8052_output/73708288_FT.csv'
    # mapping_data = 'C:/Users/user2\Desktop/Tri Le/Live score model/Autralia Capital National League/Mapping_RB2_and_OU_data/Mapping_files.csv'
    # preprocessor = Preprocess_log_data(log_url=log_url)
    # match_dict = preprocessor.convert_log_match()
    # pprint(match_dict[0])
    #
    # # Save json file
    # preprocessor.save_json(file_directory='json')

    log_file_dir = r"E:\Tri Le\Live score model\Span Primera Ferderacion\DATA\log_data_27112023\Data"
    destination_dir = r"E:\Tri Le\Live score model\Span Primera Ferderacion\DATA\json\log_data_27112023"

    log_match_path = [os.path.join(log_file_dir,f) for f in os.listdir(log_file_dir) if 'FT.csv' in f]
    for log_path in tqdm(log_match_path, desc="Starting to preprocess the Log file...."):
        preprocessor = Preprocess_log_data(log_url=log_path)
        match_dict = preprocessor.convert_log_match()
        #pprint(match_dict[0])

        # Save json file
        # preprocessor.save_json(file_directory='json/Germany_3rd_liga/')
        preprocessor.save_json(file_directory=destination_dir)


