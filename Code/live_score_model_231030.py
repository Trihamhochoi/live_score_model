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
        self.attacking_round = []  # the attacking round consist all events, start is event Safe.

        # Two target:
        self.ability_full_match_list = []  # ability list of full match, output will be  appended into this
        self.ability_json = dict()  # output after api is called
        self.full_match_list = list()

    def _calculate_attacking_round(self, data: list):
        test = pd.DataFrame(data)

        # count rows of home/away
        home_count = (test['field'] == 'home').sum()
        away_count = (test['field'] == 'away').sum()

        # Determine that this round is the counter-attack or normal attack or nothing happen
        first_event = test.iloc[0][['field', 'type']].to_dict()
        last_event = test.iloc[-1][['field', 'type']].to_dict()
        if (first_event['field'] != last_event['field']) and (first_event['type'] == 'SAFE') and (
                home_count > 0 and away_count > 0) and test.shape[0] > 2:
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
        sample = sample[features].rename(columns={'counter_attack': 'couter_attack'})

        # Apply model to predict:
        label = self.model.predict(sample)[0]

        # get percent:
        diff = self.ability_json['home_ability'] - self.ability_json['away_ability']
        # print(f"diff ability of 2 team: {diff} of Field: {self.ability_json['field']}")

        # 2 team have same ability
        if 0 <= abs(diff) < 0.5:
            mapping = {'Low': 5, 'Medium': 10, 'High': 10}
            return mapping[label]

        # a team is slightly stronger than the other team
        elif 0.5 <= abs(diff) < 1.1:
            if diff > 0:
                mapping = {'home': {'Low': 7, 'Medium': 12, 'High': 12},
                           'away': {'Low': 5, 'Medium': 10, 'High': 10}}
            else:
                mapping = {'home': {'Low': 5, 'Medium': 10, 'High': 10},
                           'away': {'Low': 7, 'Medium': 12, 'High': 12}}

            # Determine this attaching round belong which team HOME or AWAY?
            team = self.ability_json['field']
            if team is None:
                print(self.ability_json)
            return mapping[team][label]

        # a team is rapidly stronger than the other team
        elif 1.1 <= abs(diff):
            if diff > 0:
                mapping = {'home': {'Low': 10, 'Medium': 15, 'High': 15},
                           'away': {'Low': 5, 'Medium': 10, 'High': 10}}
            else:
                mapping = {'home': {'Low': 5, 'Medium': 10, 'High': 10},
                           'away': {'Low': 10, 'Medium': 15, 'High': 15}}

            # Determine this attaching round belong which team HOME or AWAY?
            team = self.ability_json['field']
            return mapping[team][label]

    def _get_next_percent(self, home: True):
        if home:
            if self.ability_full_match_list[-1]['home_p_in/de'] == 0:
                percent = self.ability_full_match_list[-1]['home_p_in/de']
                return percent

            elif self.ability_full_match_list[-1]['home_p_in/de'] != 0:
                look_back_20s = self.ability_full_match_list[-20:][::-1]

                try:
                    has_update = [d for d in look_back_20s if d['update'] is not None][0]
                    index = self.ability_full_match_list[-1]['second'] - has_update['second'] + 1
                    percent = (has_update['per_expo_array'][int(index)]) * 0.01

                    # If absolute percent is 1% => go back 0
                    if abs(percent) <= 0.01:
                        percent = 0
                    return percent

                except IndexError:
                    percent = self.ability_full_match_list[-1]['home_p_in/de']
                    return percent

        else:
            if self.ability_full_match_list[-1]['away_p_in/de'] == 0:
                percent = self.ability_full_match_list[-1]['away_p_in/de']
                return percent

            elif self.ability_full_match_list[-1]['away_p_in/de'] != 0:
                look_back_20s = self.ability_full_match_list[-20:][::-1]

                try:
                    has_update = [d for d in look_back_20s if d['update'] is not None][0]
                    index = self.ability_full_match_list[-1]['second'] - has_update['second'] + 1
                    percent = (has_update['per_expo_array'][int(index)]) * 0.01

                    # If absolute percent is smaller than 1% => go back 0
                    if abs(percent) <= 0.01:
                        percent = 0
                    return percent

                except IndexError:
                    percent = self.ability_full_match_list[-1]['away_p_in/de']
                    return percent

    # Decrease abilities of HOME/AWAY when 2 team do not attack in next 10 secs
    def decrease_both_ab(self, ability_json):
        # Three following conditions to decrease both abilities:
        # 1. there is Safe in first second of ten previous seconds
        # 2. there is not attacking event in 10 previous seconds
        # 3. there are not increased percent occurred in ten previous seconds
        # 4. this ability type is None

        lookback_ab_11s = self.ability_full_match_list[-11:]
        cond_1 = (lookback_ab_11s[0]['has_event'] == 'SAFE')
        cond_2 = all([True if ab_sec['has_event'] not in ['AT', 'DAN', 'DAT', 'SONT', 'SWW', 'DFK'] else False for ab_sec in lookback_ab_11s])
        cond_3 = all([(ab_sec['home_p_in/de'] == 0) and (ab_sec['away_p_in/de'] == 0) for ab_sec in lookback_ab_11s])
        cond_4 = ability_json['has_event'] is None

        if all([cond_1, cond_2, cond_3, cond_4]):
            exp_max = math.log(5)  # maximum decrease 5%
            decrease_both_arr = [-(math.e ** exp) for exp in np.linspace(start=0.1, stop=exp_max, num=10)]
            ability_json['home_p_in/de'] = (decrease_both_arr[0]) * 0.01
            ability_json['away_p_in/de'] = (decrease_both_arr[0]) * 0.01
            ability_json['per_expo_array'] = decrease_both_arr
            ability_json['update'] = 'decreased_both'
            ability_json['field'] = 'both'
            ability_json['home_exp_ability'] = (1 + ability_json['home_p_in/de']) * ability_json['home_ability']
            ability_json['away_exp_ability'] = (1 + ability_json['away_p_in/de']) * ability_json['away_ability']
            # print('Start to decrease the abilities of 2 teams')
            # print(ability_json)
            # print('\n')
            return ability_json
        else:
            return ability_json

    def _determine_when_attacking(self, event_dictionary):
        # Events help reset the attacking round of a team {'SAFE','Score'}
        # print(event_dictionary)
        if (event_dictionary['type'] == 'SAFE') or (event_dictionary['sec'] <= 2) or (event_dictionary['type'] == 'Score'):
            if len(self.attacking_round) == 0:
                self.attacking_round.append(event_dictionary)

            # IF the field is different in next event and type as SAFE or start new period => the opponent steals a ball => Reset the attacking round for opponent/Rival
            elif ((event_dictionary['field'] != self.attacking_round[-1]['field']) or
                  (event_dictionary['period'] != self.attacking_round[-1]['period']) or
                  (event_dictionary['field'] == self.attacking_round[-1]['field'] and self.attacking_round[-1]['type'] in ['CR'] and event_dictionary['type'] == 'SAFE')):
                self.full_match_list.append(self.attacking_round)
                self.attacking_round = list()
                self.attacking_round.append(event_dictionary)

            # IF the field is same in next event and type as SAFE, the team go back their field to implement new round. => Still count in one attacking round
            elif event_dictionary['field'] == self.attacking_round[-1]['field']:
                self.attacking_round.append(event_dictionary)

            # Determine the HOME/ AWAY percent in case start a match and restart when period 2 is starting
            # If previous event don't have any increased percent => home percent and away percent = 0
            self.ability_json['field'] = event_dictionary['field']
            if len(self.ability_full_match_list) == 0 or (event_dictionary['period'] == 2 and event_dictionary['sec'] < 2) or (event_dictionary['type'] == 'Score') or (
                    self.ability_full_match_list[-1]['home_p_in/de'] == 0 and self.ability_full_match_list[-1]['away_p_in/de'] == 0):
                self.ability_json['home_p_in/de'] = 0
                self.ability_json['away_p_in/de'] = 0
                self.ability_json['per_expo_array'] = None

            # In Case home percent increase of Home/Away percent is greater than 0=> decrease gradually
            elif self.ability_full_match_list[-1]['home_p_in/de'] > 0:
                # Get exponent for event Safe and decreased array
                max_decrease = self.ability_full_match_list[-1]['home_p_in/de']
                exp_max = math.log((max_decrease - 0.005) * 100)  # the exponent for Safe event
                decrease_array = [(math.e ** exp) for exp in np.linspace(start=exp_max, stop=0, num=10)]  # decrease in 10 sec

                # Update ability
                self.ability_json['update'] = False
                self.ability_json['away_p_in/de'] = 0
                self.ability_json['home_p_in/de'] = decrease_array[0] * 0.01
                self.ability_json['per_expo_array'] = decrease_array

            # Update Away
            elif self.ability_full_match_list[-1]['away_p_in/de'] > 0:
                # Get exponent for event Safe and decreased array
                max_decrease = self.ability_full_match_list[-1]['away_p_in/de']
                exp_max = math.log((max_decrease - 0.005) * 100)  # the exponent for Safe event
                decrease_array = [(math.e ** exp) for exp in np.linspace(start=exp_max, stop=0, num=10)]  # decrease in 10 sec

                # Update ability
                self.ability_json['update'] = False
                self.ability_json['home_p_in/de'] = 0
                self.ability_json['away_p_in/de'] = decrease_array[0] * 0.01
                self.ability_json['per_expo_array'] = decrease_array

            # Update AWAY and HOME when percent is negative
            elif self.ability_full_match_list[-1]['away_p_in/de'] < 0 and self.ability_full_match_list[-1]['home_p_in/de'] < 0:
                self.ability_json['home_p_in/de'] = 0
                self.ability_json['away_p_in/de'] = 0
                self.ability_json['per_expo_array'] = None

        # Check the next event, if event is same field, => add that event to the current round:
        elif event_dictionary['field'] == self.attacking_round[-1]['field']:
            self.attacking_round.append(event_dictionary)

            # Trigger model:
            if (event_dictionary['type'] in ['DAT', 'DAN', 'DFK']) and (self.attacking_round[-2]['type'] in ['DAT', 'DAN', 'DFK']):

                # update the ability
                self.ability_json['field'] = event_dictionary['field']
                self.ability_json['update'] = True

                # Transform to 1 attacking round from here to apply in model
                expected_percent = self._predict_percent(atk_round=self.attacking_round)

                # Find the exponent from function y = e^x => Find x?
                max_exponent = math.log(expected_percent)
                exponent_array = [(math.e ** exp) for exp in np.linspace(start=1, stop=max_exponent, num=20)]

                if event_dictionary['field'] == 'home':
                    self.ability_json['home_p_in/de'] = exponent_array[0] * 0.01
                    self.ability_json['away_p_in/de'] = 0
                    self.ability_json['per_expo_array'] = exponent_array

                else:
                    self.ability_json['home_p_in/de'] = 0
                    self.ability_json['away_p_in/de'] = exponent_array[0] * 0.01
                    self.ability_json['per_expo_array'] = exponent_array

            # IF CURRENT EVENT IS ATTACK AND PREVIOUS EVENT IS SAFE => ABILITY WILL GO BACK ZERO
            elif (event_dictionary['type'] in ['AT']) and ('SAFE' in [atk_rd['type'] for atk_rd in self.attacking_round]):
                self.ability_json['field'] = event_dictionary['field']
                self.ability_json['home_p_in/de'] = 0
                self.ability_json['away_p_in/de'] = 0
                self.ability_json['per_expo_array'] = None

            else:
                self.ability_json['field'] = event_dictionary['field']
                self.ability_json['home_p_in/de'] = self._get_next_percent(home=True)
                self.ability_json['away_p_in/de'] = self._get_next_percent(home=False)

        # In case as counterstrike, still add to that current round but this is rival's attacking round.
        elif event_dictionary['field'] != self.attacking_round[-1]['field'] and event_dictionary['type'] not in ['TI', 'CR']:

            # if team is attacking. Then next event is attack of the opponent => Start new attacking round.
            if self.attacking_round[-1]['type'] in ['AT', 'DAT', 'DAN'] and event_dictionary['type'] in ['FK', 'AT']:
                self.full_match_list.append(self.attacking_round)
                self.attacking_round = list()
                self.attacking_round.append(event_dictionary)
            else:
                self.attacking_round.append(event_dictionary)

            self.ability_json['field'] = event_dictionary['field']
            self.ability_json['home_p_in/de'] = self._get_next_percent(home=True)
            self.ability_json['away_p_in/de'] = self._get_next_percent(home=False)

        # Different field but type Throw in => the opponent get the ball
        elif event_dictionary['field'] != self.attacking_round[-1]['field'] and event_dictionary['type'] in ['TI']:
            self.ability_json['field'] = event_dictionary['field']
            self.ability_json['home_p_in/de'] = self._get_next_percent(home=True)
            self.ability_json['away_p_in/de'] = self._get_next_percent(home=False)
        else:
            print(event_dictionary)
            raise Exception('There is error in there')

    def predict_expected_ability(self, input_api_json):
        # if attacking_round_list is not None:
        #     self.attacking_round = attacking_round_list
        #     self.ability_full_match_list = ability_fullmatch_list

        self.sec_api = input_api_json
        timer = self.sec_api['Timer']

        # CURRENT EVENT
        home_cur = {k: v for k, v in self.sec_api['Event'].items() if '1' in k}
        away_cur = {k: v for k, v in self.sec_api['Event'].items() if '2' in k}
        # Re-order the event in second
        order_key_h = ['Score1', 'SAFE1', 'TI1', 'ATT1', 'DATT1', 'DAN1', 'FK1', 'DFK1', 'CR1', 'SONT1', 'SWW1']
        order_key_a = ['Score2', 'SAFE2', 'TI2', 'ATT2', 'DATT2', 'DAN2', 'FK2', 'DFK2', 'CR2', 'SONT2', 'SWW2']
        home_current = {k: home_cur[k] for k in order_key_h if k in home_cur}
        away_current = {k: away_cur[k] for k in order_key_a if k in away_cur}

        # LAST EVENT
        home_pre = {k: v for k, v in self.sec_api['LastEvent'].items() if '1' in k}
        away_pre = {k: v for k, v in self.sec_api['LastEvent'].items() if '2' in k}

        # Re-order the event in second
        home_previous = {k: home_pre[k] for k in order_key_h if k in home_pre}
        away_previous = {k: away_pre[k] for k in order_key_a if k in away_pre}

        # Ability of home and away:
        home_ability = self.sec_api['Ability']['Home']
        away_ability = self.sec_api['Ability']['Away']

        # prediction ability
        self.ability_json = {'period': timer['LivePeriod'],
                             'second': timer['LiveTimer'],
                             'field': None,
                             'has_event': None,
                             'update': None,
                             'home_p_in/de': None, 'away_p_in/de': None,
                             'home_ability': home_ability, 'home_exp_ability': None,
                             'away_ability': away_ability, 'away_exp_ability': None,
                             'per_expo_array': None  # exponent
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
                    try:
                        self._determine_when_attacking(event_dictionary=event_dict)
                    except IndexError as e:
                        print(f'There is error occurred: {e}')
                        pass

                else:
                    if len(self.ability_json) == 0:
                        is_event = False
                        update = False

            # Calculate the home/away expected ability:
            if len(self.ability_full_match_list) == 0:
                self.ability_json['home_p_in/de'] = 0
                self.ability_json['away_p_in/de'] = 0
                self.ability_json['home_exp_ability'] = self.ability_json['home_ability']
                self.ability_json['away_exp_ability'] = self.ability_json['away_ability']
            # Decrease abilities of Home and Away team when there is no attack during the match.
            elif len(self.ability_full_match_list) > 10:
                self.ability_json = self.decrease_both_ab(ability_json=self.ability_json)

            # Calculate the expected ability:
            if self.ability_json['has_event'] is not None:
                self.ability_json['home_exp_ability'] = (1 + self.ability_json['home_p_in/de']) * self.ability_json['home_ability']
                self.ability_json['away_exp_ability'] = (1 + self.ability_json['away_p_in/de']) * self.ability_json['away_ability']
            elif self.ability_json['update'] == 'decreased_both':
                pass
            elif len(self.ability_full_match_list) == 0:
                pass
            else:
                self.ability_json['field'] = self.ability_full_match_list[-1]['field']
                self.ability_json['home_p_in/de'] = self._get_next_percent(home=True)
                self.ability_json['away_p_in/de'] = self._get_next_percent(home=False)
                self.ability_json['home_exp_ability'] = (1 + self.ability_json['home_p_in/de']) * self.ability_json['home_ability']
                self.ability_json['away_exp_ability'] = (1 + self.ability_json['away_p_in/de']) * self.ability_json['away_ability']

        except Exception as e:
            raise e

        else:
            self.ability_full_match_list.append(self.ability_json)
            return self.ability_json


if __name__ == '__main__':
    # Call model
    pickle_file_path = 'model/Germany_3rd_liga/ada_live_model.sav'
    with open(pickle_file_path, 'rb') as file:
        rf_model = pickle.load(file)

    # Json of match
    # f = open('json/Australia_league/73708288_FT.json')
    f = open('json/Germany_3rd_liga/74075703_FT.json')

    # returns JSON object as a dictionary
    api_json = json.load(f)

    # Create Live model
    live_model = LiveScore_Model(model=rf_model)

    # Create atk round list and ability of full match list
    current_atk_round = None
    full_ability = None
    for idx, dict_sec in enumerate(api_json):
        ability = live_model.predict_expected_ability(input_api_json=dict_sec,
                                                      # attacking_round_list=current_atk_round,
                                                      # ability_fullmatch_list=full_ability
                                                      )

        # full_ability = ability_full_match
        # current_atk_round = atk_round

    full_ability_df = pd.DataFrame(live_model.ability_full_match_list)
    full_match_df = pd.DataFrame(data=live_model.full_match_list)
    print(full_ability_df.shape)
    print(full_match_df.shape)
