import re
import json
import pandas as pd
import numpy as np
from pprint import pprint
import pickle
import math


class LiveScore_Model:
    def __init__(self, model):
        # The model is used to predict the attacking round, which is triggered when the event is Dat/Dan/DFK
        self.model = model
        self.attacking_round = [] # the attacking round consist all events, start is event Safe.

        # Two target:
        self.ability_full_match_list = [] # ability list of full match, output will be  appended into this
        self.ability_json = dict() # output after api is called
        self.full_match_list = list()

    def _calculate_attacking_round(self, data: list):
        test = pd.DataFrame(data)

        # count rows of home/away
        home_count = (test['field'] == 'home').sum()
        away_count = (test['field'] == 'away').sum()

        # Determine that this round is the counter-attack or normal attack or nothing happen
        first_event = test.iloc[0][['field', 'type']].to_dict()
        last_event = test.iloc[-1][['field', 'type']].to_dict()
        if (first_event['field'] != last_event['field']) and (first_event['type'] == 'SAFE') and ( home_count > 0 and away_count > 0) and test.shape[0] > 2:
            counter = 1
        else:
            counter = 0

            ### IF HOME COUNT > AWAY COUNT => THIS IS THE ATTACKING ROUND OF HOME, OTHEWISE ###
        if home_count > away_count:
            one_round = test[test['field'] == 'home'].reset_index(drop=True)
            one_attacking_round = pd.pivot_table(data=one_round,
                                                 values='sec',
                                                 columns='type',
                                                 index='field',
                                                 aggfunc='count',
                                                 fill_value=0)
        elif home_count < away_count:
            one_round = test[test['field'] == 'away'].reset_index(drop=True)
            one_attacking_round = pd.pivot_table(data=one_round,
                                                 values='sec',
                                                 columns='type',
                                                 index='field',
                                                 aggfunc='count',
                                                 fill_value=0)

        # Case the Away event == home's event => there is no values which determine the event belonging to what team.
        else:
            one_round = test[test['field'] == 'home'].reset_index(drop=True)
            one_attacking_round = pd.pivot_table(data=one_round,
                                                 values='sec',
                                                 columns='type',
                                                 index='field',
                                                 aggfunc='count',
                                                 fill_value=0)

        # Drop down level of multi index
        one_attacking_round.columns = list(one_attacking_round.columns)
        one_attacking_round = one_attacking_round.reset_index()

        ### COUNTER ATTACK ###
        one_attacking_round['counter_attack'] = counter

        ### CACULATE THE ATTTACKING DURATION AND START TIME ###
        column_name = ['period', 'sec']
        # Calculate the difference between the first and last row for min and sec
        first_row = test.iloc[0][column_name]
        last_row = test.iloc[-1][column_name]

        # Calculate the period of a attacking round
        duration = (last_row['sec'] - first_row['sec'])

        # Add this value in this attacking round
        one_attacking_round['duration'] = duration

        # set start min and start sec
        one_attacking_round['period'] = first_row['period']
        one_attacking_round['start_sec'] = first_row['sec']
        return one_attacking_round

    def _predict_percent(self, atk_round: list):
        # Transform to 1 attacking round from here to apply in model
        atk_df = self._calculate_attacking_round(data=atk_round)

        # Reorder columns
        stop_index = list(atk_df.columns).index('counter_attack')
        columns_order = ['period', 'start_sec', 'duration', 'field', 'counter_attack']
        columns_order.extend(list(atk_df.columns)[1:stop_index])

        # Determine the features:
        sample = atk_df.rename(columns={'DAN': 'Danger'})
        features = ['counter_attack', 'CR', 'AT', 'DAT', 'Danger', 'DFK', 'PEN']
        for feat in features:
            if feat not in sample.columns:
                sample[feat] = 0
        sample = sample[features].rename(columns={'counter_attack':'couter_attack'})

        # Apply model to predict:
        label = self.model.predict(sample)[0]

        # get percent:
        mapping = {'Low': 5, 'Medium': 10, 'High': 15}
        return mapping[label]

    def _get_next_percent(self, home: True):
        if home:
            if self.ability_full_match_list[-1]['home_percent_increase'] == 0:
                percent = self.ability_full_match_list[-1]['home_percent_increase']
                return percent
            elif self.ability_full_match_list[-1]['home_percent_increase'] != 0:
                look_back_20s = self.ability_full_match_list[-20:][::-1]
                try:
                    has_update = [d for d in look_back_20s if d['update']][0]
                    index = self.ability_full_match_list[-1]['second'] - has_update['second'] + 1
                    percent = (math.e ** has_update['percent_exponent_array'][index]) / 100
                    return percent
                except IndexError:
                    percent = self.ability_full_match_list[-1]['home_percent_increase']
                    return percent


        else:
            if self.ability_full_match_list[-1]['away_percent_increase'] == 0:
                percent = self.ability_full_match_list[-1]['away_percent_increase']
                return percent

            elif self.ability_full_match_list[-1]['away_percent_increase'] != 0:
                look_back_20s = self.ability_full_match_list[-20:][::-1]
                try:
                    has_update = [d for d in look_back_20s if d['update']][0]
                    index = self.ability_full_match_list[-1]['second'] - has_update['second'] + 1
                    percent = (math.e ** has_update['percent_exponent_array'][index]) / 100
                    return percent
                except IndexError:
                    percent = self.ability_full_match_list[-1]['away_percent_increase']
                    return percent

    def _determine_when_attacking(self,event_dictionary):
        # Events help reset the attacking round of a team {'SAFE','Score'}
        if (event_dictionary['type'] == 'SAFE') or (event_dictionary['sec'] < 2) or (event_dictionary['type'] == 'Score'):
            if len(self.attacking_round) == 0:
                self.attacking_round.append(event_dictionary)

            # IF the field is different in next event and type as SAFE or start new period => the opponent steals a ball => Reset the attacking round for opponent/Rival
            elif (event_dictionary['field'] != self.attacking_round[-1]['field']) or (event_dictionary['period'] != self.attacking_round[-1]['period']):
                self.full_match_list.append(self.attacking_round)
                self.attacking_round = list()
                self.attacking_round.append(event_dictionary)

            # IF the field is same in next event and type as SAFE, the team go back their field to implement new round. => Still count in one attacking round
            elif event_dictionary['field'] == self.attacking_round[-1]['field']:
                self.attacking_round.append(event_dictionary)

            # percent of ability go back 0
            self.ability_json['home_percent_increase'] = 0
            self.ability_json['away_percent_increase'] = 0
            self.ability_json['percent_exponent_array'] = None

            # Check the next event, if event is same field, => add that event to the current round:
        elif event_dictionary['field'] == self.attacking_round[-1]['field']:
            self.attacking_round.append(event_dictionary)

            # Trigger model:
            if (event_dictionary['type'] in ['DAT', 'DAN', 'DFK']) and (self.attacking_round[-2]['type'] in ['DAT', 'DAN', 'DFK']):

                # Transform to 1 attacking round from here to apply in model
                #get_percent = self._predict_percent(atk_round=self.attacking_round)

                # Transform to 1 attacking round from here to apply in model
                expected_percent = self._predict_percent(atk_round=self.attacking_round)

                # Find the exponent from function y = e^x => Find x?
                max_exponent = math.log(expected_percent)
                exponent_array = np.linspace(start=1, stop=max_exponent, num=20)

                # update the ability
                self.ability_json['update'] = True
                if event_dictionary['field'] == 'home':
                    self.ability_json['home_percent_increase'] = (math.e**exponent_array[0])*0.01
                    self.ability_json['away_percent_increase'] = 0
                    self.ability_json['percent_exponent_array'] = exponent_array
                else:
                    self.ability_json['home_percent_increase'] = 0
                    self.ability_json['away_percent_increase'] = (math.e**exponent_array[0])*0.01
                    self.ability_json['percent_exponent_array'] = exponent_array
            else:
                self.ability_json['home_percent_increase'] = self._get_next_percent(home=True)
                self.ability_json['away_percent_increase'] = self._get_next_percent(home=False)

            # In case as counterstrike, still add to that current round but this is rival's attacking round.
        elif event_dictionary['field'] != self.attacking_round[-1]['field'] and event_dictionary['type'] not in ['TI','CR']:
            # if team is attacking. Then next event is attack of the opponent => Start new attacking round.
            if self.attacking_round[-1]['type'] in ['AT', 'DAT', 'DAN'] and event_dictionary['type'] in ['FK', 'AT']:
                self.full_match_list.append(self.attacking_round)
                self.attacking_round = list()
                self.attacking_round.append(event_dictionary)
            else:
                self.attacking_round.append(event_dictionary)

            self.ability_json['home_percent_increase'] = self._get_next_percent(home=True)
            self.ability_json['away_percent_increase'] = self._get_next_percent(home=False)

            # Different field but type Throw in => the opponent get the ball
        elif event_dictionary['field'] != self.attacking_round[-1]['field'] and event_dictionary['type'] in ['TI']:
            self.ability_json['home_percent_increase'] = self._get_next_percent(home=True)
            self.ability_json['away_percent_increase'] = self._get_next_percent(home=False)
        else:
            raise Exception('There is error in there')

    def predict_expected_ability(self,input_api_json, attacking_round_list=None, ability_fullmatch_list=None):
        if attacking_round_list is not None:
            self.attacking_round = attacking_round_list
            self.ability_full_match_list = ability_fullmatch_list

        self.sec_api = input_api_json
        timer = self.sec_api['Timer']

        # CURRENT EVENT
        home_current = {k: v for k, v in self.sec_api['Event'].items() if '1' in k}
        away_current = {k: v for k, v in self.sec_api['Event'].items() if '2' in k}

        # LAST EVENT
        home_previous = {k: v for k, v in self.sec_api['LastEvent'].items() if '1' in k}
        away_previous = {k: v for k, v in self.sec_api['LastEvent'].items() if '2' in k}

        # Ability of home and away:
        home_ability = self.sec_api['Ability']['Home']
        away_ability = self.sec_api['Ability']['Away']

        # prediction ability
        self.ability_json = {'period': timer['LivePeriod'],
                             'second': timer['LiveTimer'],
                             'has_event': None,
                             'update': None,
                             'home_percent_increase': None,
                             'away_percent_increase': None,
                             'home_ability': home_ability,
                             'home_exp_ability': None,
                             'away_ability': away_ability,
                             'away_exp_ability': None,
                             'percent_exponent_array': None
                             }

        try:
            # Check whether there is a event difference in each second or not.
            for idx, (h_c, h_p, a_c, a_p) in enumerate(zip(home_current, home_previous, away_current, away_previous)):
                diff_a = away_current[a_c] - away_previous[a_p]
                diff_h = home_current[h_c] - home_previous[h_p]

                if diff_a > 0 or diff_h > 0:
                    if diff_h > 0:
                        key_c = h_c
                    else:
                        key_c = a_c

                    field = 'home' if '1' in key_c else ('away' if '2' in key_c else 'unknown')
                    # Update Type
                    type_ = re.sub(pattern=r'\d', repl='', string=key_c)
                    type_ = re.sub(pattern='TT', repl='T', string=type_)

                    # Create dictionary
                    event_dict = {'period': timer['LivePeriod'],
                                  'sec': timer['LiveTimer'],
                                  'field': field,
                                  'type': type_}

                    # Check what type event
                    self.ability_json['has_event'] = event_dict['type']

                    # Determine when team attacks
                    self._determine_when_attacking(event_dictionary=event_dict)

                else:
                    if len(self.ability_json) == 0:
                        is_event = False
                        update = False

            # Calculate the home/away expected ability:
            if len(self.ability_full_match_list) == 0:
                self.ability_json['home_percent_increase'] = 0
                self.ability_json['away_percent_increase'] = 0
                self.ability_json['home_exp_ability'] = self.ability_json['home_ability']
                self.ability_json['away_exp_ability'] = self.ability_json['away_ability']
            else:
                if self.ability_json['has_event'] is not None:
                    self.ability_json['home_exp_ability'] = (1 + self.ability_json['home_percent_increase']) * self.ability_json['home_ability']
                    self.ability_json['away_exp_ability'] = (1 + self.ability_json['away_percent_increase']) * self.ability_json['away_ability']
                else:
                    self.ability_json['home_percent_increase'] = self._get_next_percent(home=True)
                    self.ability_json['away_percent_increase'] = self._get_next_percent(home=False)
                    self.ability_json['home_exp_ability'] = (1 + self.ability_json['home_percent_increase']) * self.ability_json['home_ability']
                    self.ability_json['away_exp_ability'] = (1 + self.ability_json['away_percent_increase']) * self.ability_json['away_ability']

        except Exception as e:
            raise e

        else:
            self.ability_full_match_list.append(self.ability_json)
            return self.ability_json, self.ability_full_match_list, self.attacking_round


if __name__ == '__main__':

    # Call model
    pickle_file_path = 'model/rf_model.sav'
    with open(pickle_file_path, 'rb') as file:
        rf_model = pickle.load(file)

    # Json of match
    f = open('json/matches_api.json')

    # returns JSON object as
    # a dictionary
    api_json = json.load(f)

    # Create Live model
    live_model = LiveScore_Model(model=rf_model)

    # Create atk round list and ability of full match list
    current_atk_round = None
    full_ability = None
    for idx, dict_sec in enumerate(api_json):
        ability, ability_full_match, atk_round = live_model.predict_expected_ability(input_api_json=dict_sec,
                                                                                     attacking_round_list=current_atk_round,
                                                                                     ability_fullmatch_list=full_ability)
        full_ability = ability_full_match
        current_atk_round = atk_round

    full_ability_df = pd.DataFrame(full_ability)
    print(full_ability_df.shape)