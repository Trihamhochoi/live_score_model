import os.path
from tqdm import tqdm
from live_score_model_for_log import LiveScore_Model
# Save model
import pickle
import json
import pandas as pd
import pathlib
import re

class Build_Ability_match:
    def __init__(self, model_url, api_json_url):
        # Pickle model
        with open(model_url, 'rb') as file:
            model = pickle.load(file)
        self.live_model = LiveScore_Model(model=model)

        # Json of match
        self.api_json = api_json_url
        with open(api_json_url, 'rb') as f:
            self.match_api = json.load(f)

        self.name = f'{pathlib.Path(self.api_json).stem}.csv'
    def predict_full_match(self):
        # Create atk round list and ability of full match list
        try:
            for idx, dict_sec in enumerate(self.match_api):
                ability = self.live_model.predict_expected_ability(input_api_json=dict_sec)
                # full_ability = ability_full_match
                # current_atk_round = atk_round

            #   Create dataframe
            self.full_match_df = pd.DataFrame(self.live_model.ability_match)

            # HOME TEAM
            home_ability = pd.melt(frame=self.full_match_df,
                                   id_vars=['period', 'second'],
                                   value_vars=['home_ability', 'home_exp_ability'],
                                   var_name='type_ability')

            home_ability = pd.merge(left=home_ability,
                                    right=self.full_match_df[['period', 'second', 'home_p_in/de']],
                                    on=['period', 'second'],
                                    how='left')
            # AWAY
            away_ability = pd.melt(frame=self.full_match_df,
                                   id_vars=['period', 'second'],
                                   value_vars=['away_ability', 'away_exp_ability'],
                                   var_name='type_ability')

            away_ability = pd.merge(left=away_ability,
                                    right=self.full_match_df[['period', 'second', 'away_p_in/de']],
                                    on=['period', 'second'],
                                    how='left')
            return home_ability, away_ability
        except Exception as e:
            print(f'There is error occurred in {self.name}')
            raise e

    def save_csv(self,file_directory='ability_match/'):
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
            # else:
            #     print(f"Directory '{dir_path}' already exists. Starting to execute log file and add into the corresponding directory.")

        # Check directory input
        create_directory(dir_path=file_directory)

        # Save into json file
        # Specify the file name where you want to save the JSON data
        self.full_match_df['match_id'] = pathlib.Path(self.api_json).stem.split('_')[0]
        self.full_match_df.to_csv(path_or_buf=os.path.join(file_directory,self.name),index=False)
        print(f'File is saved into directory: "{os.path.join(file_directory, self.name)}"')

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # Call model

    # AUSTRALIA LEAGUE
    #
    # api_json_files = [os.path.join('json/Australia_league', f) for f in os.listdir('json/Australia_league') if 'FT' in f]

    # GERMANY 3RD LALIGA
    # pickle_file_path = 'model/Germany_3rd_liga/rf_live_model.sav'
    # api_json_files = [os.path.join('json/Germany_3rd_liga',f) for f in os.listdir('json/Germany_3rd_liga') if 'FT' in f]


    # SPAIN LEAGUE
    #pickle_file_path = 'model/Span_Primera_Ferderacion/ada_live_model.sav'
    pickle_file_path = 'model/Australia_league/clf_adb_dt_model.sav'
    json_dir = "json/Australia_league" #r"E:\Tri Le\Live score model\Span Primera Ferderacion\DATA\json\log_data_27112023"
    ability_directory = "ability_match/Australia_league"  #r"E:\Tri Le\Live score model\Span Primera Ferderacion\DATA\ability_match/log_data_27112023"
    api_json_files = [os.path.join(json_dir, f) for f in os.listdir(json_dir) if 'FT' in f]

    for path in tqdm(api_json_files,desc='Starting to predict the expected abilities:..', position=0, leave=True):
        try:
            full_match_ability = Build_Ability_match(model_url=pickle_file_path, api_json_url=path)
            home, away = full_match_ability.predict_full_match()
        except Exception as e:
            raise e
        else:
            # Save file
            full_match_ability.save_csv(file_directory=ability_directory)
            # full_match_ability.save_csv(file_directory='ability_match/Australia_league/')


