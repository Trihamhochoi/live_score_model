import pandas as pd
import json
import numpy as np
import warnings
import re
import os
import time

pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', 50)
warnings.filterwarnings("ignore")


class Preprocess_RB2_data:
    def __init__(self, log_url, mapping_url):
        self.mapping_df = None
        self.event_match = None
        self.url = log_url
        self.mapping_url = mapping_url

    def convert_event_match(self):
        _event = (pd.read_excel(self.url).iloc[25:, ]
                  .reset_index(drop=True)
                  .drop(columns=['ID', 'Competitor 2'])
                  .rename(columns={"Country": "Time",
                                   "Competition": "Playing_time",
                                   "Game Start Time": "Event_code",
                                   "Competitor 1": "Event"})
                  )

        _event['Event_code'] = _event['Event_code'].astype('int64')

        # Get metadata of a match
        metadata = pd.read_excel(self.url).iloc[0:1, ]
        match_id = metadata.iloc[:1]["ID"][0]
        country = metadata.iloc[:1]["Country"][0]
        match_time = metadata.iloc[:1]["Game Start Time"][0]
        team_home = metadata.iloc[:1]["Competitor 1"][0]
        team_away = metadata.iloc[:1]["Competitor 2"][0]

        _event['country'] = country
        _event["file_url"] = self.url
        _event["match_time"] = match_time
        _event["match_id"] = match_id

        # Add Field Away or Home
        _event["field"] = np.where(_event["Event_code"] > 2000, "away", np.where(_event["Event_code"] > 1000,
                                                                                 "home",
                                                                                 ""))

        # Add Home/Away team name
        _event["team"] = np.where(_event["Event_code"] > 2000, team_away, np.where(_event["Event_code"] > 1000,
                                                                                   team_home,
                                                                                   "")
                                  )

        # Set period 1 and period 2
        stop_index = _event.where(_event["Event_code"] == 1).dropna(subset=["Event_code"]).index[0] if (
                len(_event[_event["Event_code"] == 1]) > 0) else 1000
        _event.loc[_event.index < stop_index, "period"] = 1
        _event.loc[_event.index > stop_index, "period"] = 2

        # Split playing time
        _event["minutes"] = _event['Playing_time'].str.split(':', expand=True)[0].astype(int)
        _event["seconds"] = _event['Playing_time'].str.split(':', expand=True)[1].astype(int)

        # Filter some specific event
        all_event_list = [2048, 1024,  # AT
                          2076, 1052,  # Danger
                          2050, 1026,  # DAT
                          1027, 2051,  # DFK
                          1028, 2052,  # FK
                          2075, 1051,  # Safe event
                          1025, 2049,  # Corner **
                          2078, 1054,  # Throw in
                          2077, 1053,  # GK
                          2066, 1042,  # Foul
                          1039, 1040, 1041, 2063, 2064, 2065,  # Shot on/off target, woodwork
                          1031, 2055,  # PEN
                          2053, 1029,  # Goal**
                          1030, 2054,  # cancel_goal
                          1, 1000  # stop period
                          ]
        match_event = _event[_event['Event_code'].isin(all_event_list)]

        # Split type of match
        match_event['type'] = match_event['Event'].str.split('  ', expand=True)[0]

        # Get Zone
        # match_event["zone"] = match_event['Event'].str.extract('(Zone [A-Z]+[0-9]*)',expand=False)

        # Some specific case: GOAL: extract goal
        goal_filter = match_event['Event_code'].isin([1029, 2053])
        if goal_filter.any():
            match_event.loc[goal_filter, 'type'] = match_event[goal_filter]['Event'].str.split('  ', expand=True)[1]
            match_event.loc[goal_filter, 'info'] = match_event[goal_filter]['Event'].str.split('  ', expand=True)[0]

        cancel_goal_filter = match_event['Event_code'].isin([1030, 2054])
        if cancel_goal_filter.any():
            match_event.loc[cancel_goal_filter, 'type'] = \
                match_event[cancel_goal_filter]['Event'].str.split('  ', expand=True)[1]
            match_event.loc[cancel_goal_filter, 'info'] = \
                match_event[cancel_goal_filter]['Event'].str.split('  ', expand=True)[0]

        # Get side of corner
        corner_filter = match_event['Event_code'].isin([1025, 2049])
        if corner_filter.any():
            match_event.loc[corner_filter, 'info'] = match_event[corner_filter]['Event'].str.extract(
                pat=r'\(\w+\s-\s(.+)\)').squeeze()

        # Drop some columns
        match_event = match_event.drop(columns=['Time'])

        # Update the time datatype
        match_event['match_time'] = pd.to_datetime(match_event['match_time'], format='%d.%m.%Y - %H:%M')

        feat = ['country', 'file_url', 'match_time', 'match_id', 'Event', 'Event_code', 'team', 'field',
                'Playing_time', 'period', 'minutes', 'seconds', 'type', 'info']

        self.event_match = match_event[feat].reset_index(drop=True)
        return self.event_match

    def create_mapping_df(self):
        # Mapping between home_id,home_name,away_id,away_name of RB2 vs team_home_id,team_home_name,team_away_id,team_away_name of Taiwan team
        mapping = pd.read_csv(self.mapping_url)

        home_team = mapping[['home_id', 'home_name', 'team_home_id', 'team_home_name']].rename(
            columns={'home_id': 'rb2_id',
                     'home_name': 'rb2_name',
                     'team_home_id': 'ibc_id',
                     'team_home_name': 'ibc_team'})

        away_team = mapping[['away_id', 'away_name', 'team_away_id', 'team_away_name']].rename(
            columns={'away_id': 'rb2_id',
                     'away_name': 'rb2_name',
                     'team_away_id': 'ibc_id',
                     'team_away_name': 'ibc_team'})

        self.mapping_df = (pd.concat([home_team, away_team], axis=0)
                           .drop_duplicates(subset=['rb2_id', 'ibc_id'], keep='last')
                           .sort_values(by=['rb2_id'])
                           .reset_index(drop=True))
        return self.mapping_df

    def preprocessing_into_cumulative_df(self):
        # Merge the evnet data vs mapping df
        self.event_match = self.event_match.drop_duplicates(subset=['Playing_time', 'Event_code', 'match_id',
                                                                    'country', 'field', 'team', 'period', 'type',
                                                                    'minutes', 'seconds'])
        self.event_map_match = pd.merge(left=self.event_match,
                                        right=self.mapping_df,
                                        left_on='team',
                                        right_on='rb2_name',
                                        how='left').drop(columns=['rb2_name'])

        # Get specific columns
        feat = ['country', 'file_name', 'match_id', 'match_time', 'period',
                'minutes', 'seconds', 'team_id', 'ibc_id', 'team', 'field', 'type']
        self.event_map_match['type'] = self.event_map_match['type'].str.strip()
        self.event_map_match = self.event_map_match[feat].sort_values(by=['match_id', 'period', 'minutes', 'seconds'],
                                                                      ascending=True).reset_index(drop=True)

        # Convert type into event
        event_dummy = pd.get_dummies(data= self.event_map_match['type'])
        event_dummy = event_dummy.replace(to_replace={True: 1, False: 0})

        # Concat with event map match
        final_event = pd.concat([event_for_running, event_dummy], axis=1).drop(columns=['country', 'team','team_id', 'stop_period'])


if __name__ == '__main__':
    rb2_url = r"C:\Users\user2\Desktop\Tri Le\Live score model\Autralia Capital National League\RB2_data\2023\70.xls"
    mapping_data = 'C:/Users/user2\Desktop/Tri Le/Live score model/Autralia Capital National League/Mapping_RB2_and_OU_data/Mapping_files.csv'
    preprocessor = Preprocess_RB2_data(log_url=rb2_url, mapping_url=mapping_data)
    df = preprocessor.convert_event_match()
    mapping_df_ = preprocessor.create_mapping_df()
