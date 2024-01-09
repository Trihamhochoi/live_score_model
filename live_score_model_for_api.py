import re
import json
import pandas as pd
import numpy as np
from pprint import pprint
import pickle
import math
from tqdm import tqdm
import os


class LiveScore_Model:
    def __init__(self, model):
        # ------------------------------------------------------------------------- #
        # DEFINE PARAMETER:
        # The model is used to predict the attacking round, which is triggered when the event is Dat/Dan/DFK
        self.model = model
        self.timer_15m = 0
        self.decrease_percent = 3
        self.attacking_round = []  # the attacking round consist all events, start is event Safe.

        # Two target:
        self.ability_match = []  # ability list of full match, output will be  appended into this
        self.ability_json = dict()  # output after api is called
        self.full_match_sep = list()
        self.full_atk_rd_match = list()

    def _calculate_attacking_round(self, data: list):
        """
        Convert all event into a comprehensive attacking round
        :param data: list of events in the current round
        :return: a dictionary of one_attacking_round
        """
        test = pd.DataFrame(data)

        # count rows of home/away
        home_count = (test['field'] == 'home').sum()
        away_count = (test['field'] == 'away').sum()

        # Determine that this round is the counter-attack or normal attack or nothing happen
        first_event = test.iloc[0][['field', 'type']].to_dict()
        last_event = test.iloc[-1][['field', 'type']].to_dict()
        if (first_event['field'] != last_event['field']) and (first_event['type'] == 'SAFE') and (home_count > 0 and away_count > 0) and test.shape[0] > 2:
            counter = 1
        else:
            counter = 0

        # ----------------------------------------------------------------------------#
        # IF HOME COUNT > AWAY COUNT => THIS IS THE ATK ROUND OF HOME, ELSE, THIS IS AWAY ATK ROUND
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
        """
        Determine the probability of that attacking round whether is low/high danger
        :param atk_round: list of attacking round
        :return: the percent model predict
        """
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

        # Calculate the difference between initial abilities:
        diff = self.ability_json['home_ability'] - self.ability_json['away_ability']

        # 2 team have same ability
        if 0 <= abs(diff) < 0.5:
            mapping = {'Low': 4, 'Medium': 8, 'High': 8}
            return mapping[label]

        # a team is slightly stronger than the other team
        elif 0.5 <= abs(diff):
            if diff > 0:
                mapping = {'home': {'Low': 6, 'Medium': 10, 'High': 10},
                           'away': {'Low': 4, 'Medium': 8, 'High': 8}}
            else:
                mapping = {'home': {'Low': 4, 'Medium': 8, 'High': 8},
                           'away': {'Low': 6, 'Medium': 10, 'High': 10}}

            # Determine this attaching round belong which team HOME or AWAY?
            team = self.ability_json['field']
            if team is None:
                print(self.ability_json)
            return mapping[team][label]

    def _get_next_in_de_percent(self, home: True):
        """
        Calculate the increased/decreased percent, if previous event is triggered some points: Danger attack, Safe in 10 secs
        :param home: bool. If True, will calculate for Home Team, else Away team
        :return: Percent of next second
        """
        if home:
            if self.ability_match[-1]['home_p_in/de'] == 0:
                in_de_percent = self.ability_match[-1]['home_p_in/de']
                return in_de_percent

            # ------------------------------------------------#
            # STARTING THE ATK ROUND OR DECREASE ROUND
            elif self.ability_match[-1]['home_p_in/de'] != 0:
                look_back_20s = self.ability_match[-20:][::-1]

                try:
                    # ------------------------------------------------------#
                    # UPDATE THE INCREASE/DECREASE IN ATTACKING ROUND
                    has_update = [d for d in look_back_20s if d['update'] is not None][0]
                    index = self.ability_match[-1]['second'] - has_update['second'] + 1
                    in_de_percent = (has_update['per_expo_array'][int(index)]) * 0.01

                    # If absolute percent is 0.6% => go back 0
                    if abs(in_de_percent) <= 0.006:
                        in_de_percent = 0
                    return in_de_percent

                except IndexError:
                    in_de_percent = self.ability_match[-1]['home_p_in/de']
                    return in_de_percent
        # AWAY
        else:
            if self.ability_match[-1]['away_p_in/de'] == 0:
                in_de_percent = self.ability_match[-1]['away_p_in/de']
                return in_de_percent

            # ------------------------------------------------#
            # STARTING THE ATK ROUND OR DECREASE ROUND
            elif self.ability_match[-1]['away_p_in/de'] != 0:
                look_back_20s = self.ability_match[-20:][::-1]
                try:
                    # ------------------------------------------------------#
                    # UPDATE THE INCREASE/DECREASE IN ATTACKING ROUND
                    has_update = [d for d in look_back_20s if d['update'] is not None][0]
                    index = self.ability_match[-1]['second'] - has_update['second'] + 1
                    in_de_percent = (has_update['per_expo_array'][int(index)]) * 0.01
                    # If absolute percent is smaller than 0.6% => go back 0
                    if abs(in_de_percent) <= 0.006:
                        in_de_percent = 0
                    return in_de_percent

                except IndexError:
                    in_de_percent = self.ability_match[-1]['away_p_in/de']
                    return in_de_percent

    # Decrease abilities of HOME/AWAY when 2 team do not attack in next 10 secs
    def _decrease_both_ab(self, ability_json, current_score):
        """
        Three following conditions to decrease both abilities:
            1. there is Safe in first second of 11 or 15 previous seconds
            2. there is not attacking event in 20 previous seconds
            3. there are not increased percent occurred in ten previous seconds
            4. this ability type is None
        
        :param ability_json: dictionary
        :return: ability_json is adjusted (dictionary)
        """
        try:
            lookback_ab_20s = self.ability_match[-21:]
            lookback_ab_25s = self.ability_match[(-21 - 4):]
            cond_1_1 = (lookback_ab_20s[0]['has_event'] == 'SAFE') and (lookback_ab_20s[0]['update'] is None)
            cond_1_2 = (lookback_ab_25s[0]['has_event'] == 'SAFE') and (lookback_ab_25s[0]['update'] is False)

            cond_2 = all([True if ab_sec['has_event'] not in ['AT', 'DAN', 'DAT', 'SHG', 'SHW', 'DFK', 'FK'] else False for ab_sec in lookback_ab_20s])
            cond_3 = all([(ab_sec['home_p_in/de'] == 0) and (ab_sec['away_p_in/de'] == 0) for ab_sec in lookback_ab_20s])
            cond_4 = ability_json['has_event'] is None

            if all([cond_1_1, cond_2, cond_3, cond_4]) or all([cond_1_2, cond_2, cond_3, cond_4]):
                if (15 * 60) <= current_score['second'] < (40 * 60) and current_score['period'] == 2 and (current_score['away'] + current_score['home'] == 0):
                    negative_percent = self.decrease_percent + 1
                elif (40 * 60) < current_score['second'] and current_score['period'] == 2 and (current_score['away'] + current_score['home'] == 0):
                    negative_percent = self.decrease_percent + 1.5
                elif (
                        (current_score['second'] < (10 * 60) and abs(current_score['home'] - current_score['away']) >= 1)
                        or (abs(current_score['home'] - current_score['away']) >= 2)
                ):
                    deducted_amt = (abs(current_score['home'] - current_score['away']) - 2)  # goal diff is in [1,2] => still deducted 1%, if goal diff is 3 => deducted 2%
                    deducted_amt = deducted_amt if deducted_amt > 0 else 0
                    negative_percent = self.decrease_percent - 0.5 - deducted_amt
                    negative_percent = negative_percent if negative_percent > 0 else 1
                else:
                    negative_percent = self.decrease_percent

                # Calculate the decreased array
                exp_max = math.log(negative_percent)
                decrease_both_arr = [-(math.e ** exp) for exp in np.linspace(start=-0.4, stop=exp_max, num=20)]  # decrease gradually 20 secs

                # calculate the decrease percent
                ability_json['home_p_in/de'] = (decrease_both_arr[0]) * 0.01
                ability_json['away_p_in/de'] = (decrease_both_arr[0]) * 0.01
                ability_json['per_expo_array'] = decrease_both_arr

                # Update the other key features:
                ability_json['update'] = 'decreased_both'
                ability_json['field'] = 'both'

                # Calculate the expected ability of both team
                ability_json['home_exp_ability'] = (1 + ability_json['home_p_in/de']) * ability_json['home_ability']
                ability_json['away_exp_ability'] = (1 + ability_json['away_p_in/de']) * ability_json['away_ability']
                return ability_json
            else:
                return ability_json
        except IndexError as e:
            return ability_json

    def _transform_atk_rd(self, atk_round):
        """
        Combine all event into one attacking round 
        :param atk_round: the attacking round was finished 
        :return: a attacking round (dataframe) which applied to measure the performance
        """
        a_df = self._calculate_attacking_round(atk_round)
        # Convert start_sec to min and sec
        a_df['_mins'] = round(a_df['start_sec'] // 60)
        a_df['_secs'] = a_df['start_sec'] - a_df['_mins'] * 60

        # Determine the features:
        sample = a_df  # [columns_order]
        # .rename(columns={'DAN':'Danger'})
        features = ['period', 'start_sec', '_mins', '_secs', 'duration', 'field', 'counter_attack',
                    'SAFE', 'TI', 'CR', 'AT', 'DAT', 'DAN', 'FK', 'DFK', 'PEN', 'Score', 'SHG', 'SHW']
        for feat in features:
            if feat not in sample.columns:
                sample[feat] = 0
        sample['goal_ab'] = sample['Score'] + sample['SHG'] * 0.5 + sample['SHW'] * 0.8
        features.append('goal_ab')
        sample = sample[features].drop(columns=['Score', 'SHG', 'SHW'])
        return sample

    def _measure_team_performance(self,
                                  period):
        """
        According to the ATK rounds, which are calculated before, measure the Home/Away team’s performance to create the performance percent
        (Criteria: if there are more than 5 attacking round, the performance percent will be calculated)
        :param period::
        :return:
        """
        # Calculate the diff of ability to determine with team is evaluated better.
        home_ab = self.ability_json['home_ability']
        away_ab = self.ability_json['away_ability']
        diff_ab = home_ab - away_ab

        # Start to collect the Home attacking round and Away attacking round.
        full_match_df = pd.concat(self.full_atk_rd_match).reset_index(drop=True)
        full_match_df = full_match_df[full_match_df['period'] == period]
        home_atk = full_match_df[(full_match_df['field'] == 'home') & ((full_match_df['DAT'] > 0) | (full_match_df['DFK'] > 0))].reset_index()
        away_atk = full_match_df[(full_match_df['field'] == 'away') & ((full_match_df['DAT'] > 0) | (full_match_df['DFK'] > 0))].reset_index()

        # Calculate home shot:
        if home_atk.shape[0] > 0:
            home_shot = full_match_df[(full_match_df['field'] == 'home') & (full_match_df['goal_ab'] > 0)]
            home_perf_score = float(home_shot['goal_ab'].sum()) / home_atk.shape[0]
        else:
            home_perf_score = 0

        # Calculate away shot:
        if away_atk.shape[0] > 0:
            away_shot = full_match_df[(full_match_df['field'] == 'away') & (full_match_df['goal_ab'] > 0)]
            away_perf_score = float(away_shot['goal_ab'].sum()) / away_atk.shape[0]
        else:
            away_perf_score = 0

        try:
            if (home_perf_score - away_perf_score) != 0:
                diff_perf_percent = (home_perf_score - away_perf_score) * 100
                if diff_perf_percent > 0 > diff_ab:
                    alpha = math.log(abs(diff_perf_percent))
                    if alpha > 2:
                        alpha = 2
                    alpha_perf = {'home': alpha,
                                  'away': -alpha}

                elif diff_perf_percent < 0 < diff_ab:
                    alpha = math.log(abs(diff_perf_percent))
                    if alpha > 2:
                        alpha = 2
                    alpha_perf = {'home': -alpha,
                                  'away': alpha}
                else:
                    alpha_perf = {'home': 0,
                                  'away': 0}
            else:
                alpha_perf = {'home': 0,
                              'away': 0}

            return alpha_perf
        except Exception as e:
            print(f'home performance: {home_perf_score} - Away performance {away_perf_score}')
            raise e

    def _get_next_perf_per(self, home: True):
        """
        Get the performed percent of next second
        :param home: bool [True, False]
        """
        perf_percent = 0
        if home:
            if self.ability_match[-1]['home_perf_coef'] in [0, None] and self.ability_match[-1]['away_perf_coef'] in [0, None]:
                perf_percent = 0

            elif (self.ability_match[-1]['home_perf_coef'] != 0 and
                  self.ability_match[-1]['away_perf_coef'] == 0) or (self.ability_match[-1]['home_perf_coef'] == 0 and
                                                                     self.ability_match[-1]['away_perf_coef'] != 0):
                if self.ability_json['home_p_in/de'] == 0 and self.ability_json['away_p_in/de'] == 0:
                    perf_percent = 0
                else:
                    perf_percent = self.ability_match[-1]['home_perf_coef']

            elif self.ability_match[-1]['home_perf_coef'] <= 0 and self.ability_match[-1]['away_perf_coef'] <= 0:
                perf_percent = 0

            return perf_percent

        # AWAY
        else:
            if self.ability_match[-1]['home_perf_coef'] in [0, None] and self.ability_match[-1]['away_perf_coef'] in [0, None]:
                perf_percent = 0

            elif (self.ability_match[-1]['home_perf_coef'] == 0
                  and self.ability_match[-1]['away_perf_coef'] != 0) or (self.ability_match[-1]['home_perf_coef'] != 0
                                                                         and self.ability_match[-1]['away_perf_coef'] == 0):
                if self.ability_json['home_p_in/de'] == 0 and self.ability_json['away_p_in/de'] == 0:
                    perf_percent = 0
                else:
                    perf_percent = self.ability_match[-1]['away_perf_coef']

            elif self.ability_match[-1]['home_perf_coef'] <= 0 and self.ability_match[-1]['away_perf_coef'] <= 0:
                perf_percent = 0

            return perf_percent

    def _determine_various_cases(self, event_dictionary, current_score):
        """
        Define all cases can occur:
        - Which case when the percent of abilities increase/decrease
        - Which case performance percent increase/decrease

        :param event_dictionary: We determine the current event dictionary,
        :param current_score: the score of both teams at that time
        :return: Applied some calculation in expected abilities
        """
        # ---------------------------------------------------------------------------------------------------------#
        # Events help reset the attacking round of a team {'SAFE','Score'}
        if (event_dictionary['type'] == 'SAFE') or (event_dictionary['sec'] <= 2) or (event_dictionary['type'] == 'Score'):
            # DETERMINE THE ATTACKING ROUND
            if len(self.attacking_round) == 0:
                self.attacking_round.append(event_dictionary)

            # IF the field is different in next event and type as SAFE or start new period => the opponent steals a ball => Reset the attacking round for opponent/Rival
            elif ((event_dictionary['field'] != self.attacking_round[-1]['field']) or
                  (event_dictionary['period'] != self.attacking_round[-1]['period']) or
                  (event_dictionary['type'] == 'SAFE')):  # event_dictionary['field'] == self.attacking_round[-1]['field'] and self.attacking_round[-1]['type'] in ['CR'] and
                atk_rd_df = self._transform_atk_rd(atk_round=self.attacking_round)
                self.full_atk_rd_match.append(atk_rd_df)

                self.full_match_sep.append(self.attacking_round)
                self.attacking_round = list()
                self.attacking_round.append(event_dictionary)

            # IF the field is same in next event and type as SAFE, the team go back their field to implement new round. => Still count in one attacking round
            elif event_dictionary['field'] == self.attacking_round[-1]['field']:
                self.attacking_round.append(event_dictionary)

            # --------------------------------------------------------------------------------------------#
            # HANDLE THE ABILITY PERCENT
            # Determine the HOME/ AWAY percent in case start a match and restart when period 2 is starting => BACK TO ZERO
            # IF PREVIOUS EVENT DON'T HAVE ANY INCREASED PERCENT => HOME PERCENT AND AWAY PERCENT = 0
            self.ability_json['field'] = event_dictionary['field']
            if (
                    len(self.ability_match) == 0 or
                    (event_dictionary['period'] == 2 and event_dictionary['sec'] < 2) or
                    (event_dictionary['type'] == 'Score') or
                    (self.ability_match[-1]['home_p_in/de'] == 0 and self.ability_match[-1]['away_p_in/de'] == 0)
            ):
                self.ability_json['home_p_in/de'], self.ability_json['home_perf_coef'] = 0, 0
                self.ability_json['away_p_in/de'], self.ability_json['away_perf_coef'] = 0, 0
                self.ability_json['per_expo_array'] = None

            # In Case home percent increase of Home/Away percent is greater than 0=> decrease gradually
            elif self.ability_match[-1]['home_p_in/de'] > 0:
                # Get exponent for event Safe and decreased array
                max_decrease = self.ability_match[-1]['home_p_in/de']
                try:
                    exp_max = math.log((max_decrease - 0.002) * 100)  # the exponent for Safe event
                except ValueError:
                    exp_max = math.log(max_decrease * 100)

                decrease_array = [(math.e ** exp) for exp in np.linspace(start=exp_max, stop=-0.6, num=5)]  # decrease in 5 sec

                # Update percent increase in ATK round
                self.ability_json['update'] = False
                self.ability_json['away_p_in/de'] = 0
                self.ability_json['home_p_in/de'] = decrease_array[0] * 0.01
                self.ability_json['per_expo_array'] = decrease_array

                # Update percent in Performance
                if self.ability_match[-1]['home_perf_coef'] < 0 and self.ability_match[-1]['away_perf_coef'] < 0:
                    self.ability_json['home_perf_coef'] = 0
                    self.ability_json['away_perf_coef'] = 0
                else:
                    self.ability_json['away_perf_coef'] = 0
                    self.ability_json['home_perf_coef'] = self.ability_match[-1]['home_perf_coef']

            # Update Away
            elif self.ability_match[-1]['away_p_in/de'] > 0:
                # Get exponent for event Safe and decreased array
                max_decrease = self.ability_match[-1]['away_p_in/de']
                try:
                    exp_max = math.log((max_decrease - 0.002) * 100)  # the exponent for Safe event
                except ValueError:
                    exp_max = math.log(max_decrease * 100)

                decrease_array = [(math.e ** exp) for exp in np.linspace(start=exp_max, stop=-0.6, num=5)]  # decrease in 5 sec

                # Update increased percent of ATK round
                self.ability_json['update'] = False
                self.ability_json['home_p_in/de'] = 0
                self.ability_json['away_p_in/de'] = decrease_array[0] * 0.01
                self.ability_json['per_expo_array'] = decrease_array

                # Update Performance percent
                if self.ability_match[-1]['home_perf_coef'] < 0 and self.ability_match[-1]['away_perf_coef'] < 0:
                    self.ability_json['home_perf_coef'] = 0
                    self.ability_json['away_perf_coef'] = 0
                else:
                    self.ability_json['home_perf_coef'] = 0
                    self.ability_json['away_perf_coef'] = self.ability_match[-1]['away_perf_coef']

            # Update AWAY and HOME when percent is negative
            elif self.ability_match[-1]['away_p_in/de'] < 0 and self.ability_match[-1]['home_p_in/de'] < 0:
                self.ability_json['home_p_in/de'] = 0
                self.ability_json['away_p_in/de'] = 0
                self.ability_json['per_expo_array'] = None

        # --------------------------------------------------------------------------------------------#
        # Check the next event, if event is same field, => add that event to the current round:
        elif event_dictionary['field'] == self.attacking_round[-1]['field']:
            # DETERMINE THE ATTACKING ROUND
            self.attacking_round.append(event_dictionary)

            # --------------- #
            # TRIGGER MODEL
            if (event_dictionary['type'] in ['DAT', 'DAN', 'DFK']) and (self.attacking_round[-2]['type'] in ['DAT', 'DAN', 'DFK']):

                # update the ability
                self.ability_json['field'] = event_dictionary['field']
                self.ability_json['update'] = True

                # Transform to 1 attacking round from here to apply in model
                expected_percent = self._predict_percent(atk_round=self.attacking_round)

                # Determine the increase/decrease percent level
                if (15 * 60) <= current_score['second'] < (40 * 60) and (current_score['away'] + current_score['home'] == 0):
                    expected_percent = expected_percent / 2
                elif (40 * 60) < current_score['second'] and (current_score['away'] + current_score['home'] == 0):
                    expected_percent = expected_percent / 2.5
                elif (current_score['home'] - current_score['away']) >= 2 and self.ability_json['field'] == 'away':
                    diff = current_score['home'] - current_score['away'] - 1
                    expected_percent = expected_percent - diff
                    if expected_percent < 1:
                        expected_percent = 1
                elif (current_score['away'] - current_score['home']) >= 2 and self.ability_json['field'] == 'home':
                    diff = current_score['away'] - current_score['home'] - 1
                    expected_percent = expected_percent - diff
                    if expected_percent < 1:
                        expected_percent = 1

                # Find the exponent from function y = e^x => Find x?
                max_exponent = math.log(expected_percent)
                exponent_array = [(math.e ** exp) for exp in np.linspace(start=-0.5, stop=max_exponent, num=20)]

                # ------------------------------------------------#
                # MEASURE THE ATTACKING PERFORMANCE OF BOTH TEAM:
                if len(self.full_atk_rd_match) > 0:
                    perf_dict = self._measure_team_performance(period=self.ability_json['period'])

                else:
                    perf_dict = {'home': 0, 'away': 0}

                if event_dictionary['field'] == 'home':
                    self.ability_json['home_p_in/de'] = exponent_array[0] * 0.01
                    self.ability_json['away_p_in/de'], self.ability_json['away_perf_coef'] = 0, 0
                    self.ability_json['per_expo_array'] = exponent_array
                    self.ability_json['home_perf_coef'] = perf_dict['home'] * 0.01

                else:
                    self.ability_json['away_p_in/de'] = exponent_array[0] * 0.01
                    self.ability_json['home_p_in/de'], self.ability_json['home_perf_coef'] = 0, 0
                    self.ability_json['per_expo_array'] = exponent_array
                    self.ability_json['away_perf_coef'] = perf_dict['away'] * 0.01

            # ---------------------------------------------------------------------------------- #
            # IF CURRENT EVENT IS ATTACK AND PREVIOUS EVENT IS SAFE => ABILITY WILL GO BACK ZERO
            elif (event_dictionary['type'] in ['AT', 'DFK']) and ('SAFE' in [atk_rd['type'] for atk_rd in self.attacking_round]):
                self.ability_json['field'] = event_dictionary['field']
                self.ability_json['home_p_in/de'], self.ability_json['home_perf_coef'] = 0, 0
                self.ability_json['away_p_in/de'], self.ability_json['away_perf_coef'] = 0, 0
                self.ability_json['per_expo_array'] = None

            else:
                # Update the in/de percent of this attacking round
                self.ability_json['field'] = event_dictionary['field']
                self.ability_json['home_p_in/de'] = self._get_next_in_de_percent(home=True)
                self.ability_json['away_p_in/de'] = self._get_next_in_de_percent(home=False)

                # Update the efficient percent at that moment
                self.ability_json['home_perf_coef'] = self._get_next_perf_per(home=True)
                self.ability_json['away_perf_coef'] = self._get_next_perf_per(home=False)

        # -------------------------------------------------------------------------------------------------- #
        # IN CASE AS COUNTERSTRIKE, STILL ADD TO THAT CURRENT ROUND BUT THIS IS RIVAL'S ATTACKING ROUND.
        elif event_dictionary['field'] != self.attacking_round[-1]['field'] and event_dictionary['type'] not in ['TI', 'CR']:

            # If team is attacking. Then the next event is attack of the opponent => Start new attacking round.
            if self.attacking_round[-1]['type'] in ['AT', 'DAT', 'DAN', 'CR'] and event_dictionary['type'] in ['FK', 'AT']:
                # transform the atk round and append in full_atk_rd_match
                atk_rd_df = self._transform_atk_rd(atk_round=self.attacking_round)
                self.full_atk_rd_match.append(atk_rd_df)

                # just append all event into separated list
                self.full_match_sep.append(self.attacking_round)
                self.attacking_round = list()
                self.attacking_round.append(event_dictionary)
            else:
                self.attacking_round.append(event_dictionary)

            # ---------------------------------------------------------------------------------- #
            # IF CURRENT EVENT IS ATTACK AND PREVIOUS EVENT IS SAFE => ABILITY WILL GO BACK ZERO
            if (event_dictionary['type'] in ['AT', 'DFK']) and ('SAFE' in [atk_rd['type'] for atk_rd in self.attacking_round]):
                self.ability_json['field'] = event_dictionary['field']
                self.ability_json['home_p_in/de'], self.ability_json['home_perf_coef'] = 0, 0
                self.ability_json['away_p_in/de'], self.ability_json['away_perf_coef'] = 0, 0
                self.ability_json['per_expo_array'] = None
            else:
                # Update the in/de percent of this attacking round
                self.ability_json['field'] = event_dictionary['field']
                self.ability_json['home_p_in/de'] = self._get_next_in_de_percent(home=True)
                self.ability_json['away_p_in/de'] = self._get_next_in_de_percent(home=False)

                # Update the efficient percent at that moment
                self.ability_json['home_perf_coef'] = self._get_next_perf_per(home=True)
                self.ability_json['away_perf_coef'] = self._get_next_perf_per(home=False)

        # ----------------------------------------------------------------- #
        # DIFFERENT FIELD BUT TYPE THROW IN => THE OPPONENT GET THE BALL
        elif event_dictionary['field'] != self.attacking_round[-1]['field'] and event_dictionary['type'] in ['TI']:
            # Update the in/de percentage of this attacking round
            self.ability_json['field'] = event_dictionary['field']
            self.ability_json['home_p_in/de'] = self._get_next_in_de_percent(home=True)
            self.ability_json['away_p_in/de'] = self._get_next_in_de_percent(home=False)

            # Update the efficient percent at that moment
            self.ability_json['home_perf_coef'] = self._get_next_perf_per(home=True)
            self.ability_json['away_perf_coef'] = self._get_next_perf_per(home=False)
        else:
            # Update the in/de percentage of this attacking round
            self.ability_json['field'] = event_dictionary['field']
            self.ability_json['home_p_in/de'] = self._get_next_in_de_percent(home=True)
            self.ability_json['away_p_in/de'] = self._get_next_in_de_percent(home=False)

            # Update the efficient percentage at that moment
            self.ability_json['home_perf_coef'] = self._get_next_perf_per(home=True)
            self.ability_json['away_perf_coef'] = self._get_next_perf_per(home=False)

            raise Exception(f'There is error in there: \n{self.attacking_round}\n{event_dictionary}')

    def predict_expected_ability(self, input_api_json):
        """
        According to the input API dictionary, it helps preprocess the input.
        Then checking the difference of current events and predicting the expected abilities of both teams.
        Please refer the workflow for more details

        :param input_api_json:
        :return: Ability_dictionary
        """
        # TIMER
        timer = input_api_json['ingame_Timer']

        # CURRENT EVENT
        home_cur = {k: v for k, v in input_api_json['Event'].items() if '1' in k}
        away_cur = {k: v for k, v in input_api_json['Event'].items() if '2' in k}

        # Re-order the event in second
        order_key_h = ['SHG1', 'SHW1', 'Score1', 'SAFE1', 'TI1', 'AT1', 'DAT1', 'DAN1', 'FK1', 'DFK1', 'CR1']
        order_key_a = ['SHG2', 'SHW2', 'Score2', 'SAFE2', 'TI2', 'AT2', 'DAT2', 'DAN2', 'FK2', 'DFK2', 'CR2']
        home_current = {k: home_cur[k] for k in order_key_h if k in home_cur}
        away_current = {k: away_cur[k] for k in order_key_a if k in away_cur}

        current_score = {'period': timer['in_game_period'],
                         'second': timer['in_game_timer'],
                         'home': home_current['Score1'],
                         'away': away_current['Score2']}

        # LAST EVENT
        home_pre = {k: v for k, v in input_api_json['LastEvent'].items() if '1' in k}
        away_pre = {k: v for k, v in input_api_json['LastEvent'].items() if '2' in k}
        # Re-order the event in second
        home_previous = {k: home_pre[k] for k in order_key_h if k in home_pre}
        away_previous = {k: away_pre[k] for k in order_key_a if k in away_pre}
        # Ability of home and away:
        home_ability = input_api_json['Ability']['Home']
        away_ability = input_api_json['Ability']['Away']

        # EXPECTED ABILITY PREDICTION
        self.ability_json = {'period': timer['in_game_period'],
                             'second': timer['in_game_timer'],
                             'field': None,
                             'has_event': None,
                             'update': None,
                             'home_p_in/de': None, 'away_p_in/de': None,
                             'home_perf_coef': None, 'away_perf_coef': None,
                             'home_ability': home_ability, 'home_exp_ability': None,
                             'away_ability': away_ability, 'away_exp_ability': None,
                             'per_expo_array': None  # exponent
                             }

        try:
            # Check whether there is a event difference in each second or not.
            for idx, (h_c, h_p, a_c, a_p) in enumerate(zip(home_current,
                                                           home_previous,
                                                           away_current,
                                                           away_previous)):

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
                    event_dict = {'period': timer['in_game_period'],
                                  'sec': timer['in_game_timer'],
                                  'field': field,
                                  'type': type_}

                    # Check what type event
                    self.ability_json['has_event'] = event_dict['type']

                    # Determine when team attacks
                    try:
                        self._determine_various_cases(event_dictionary=event_dict, current_score=current_score)

                    except IndexError as e:
                        print(f'There is error occurred: {e}')  # Can pass because in some case, the timer doesn't start from beginning
                        pass

            # --------------------------------------------------------------------------------------------- #
            # IF AFTER 15 MINUTES, PERFORMANCE OF BOTH TEAM ARE 0 => DECREASE BOTH TEAM'S PERFORMANCE
            if self.ability_json['period'] == 2 and self.ability_json['second'] <= 2:
                self.timer_15m = 0
                self.decrease_percent = 3
            elif self.ability_json['has_event'] in ['SHG', 'Score', 'SHW']:
                self.timer_15m = 0
                self.decrease_percent = 3
                self.ability_json['home_perf_coef'] = 0
                self.ability_json['away_perf_coef'] = 0
            elif self.ability_json['home_perf_coef'] in [0, None] and self.ability_json['away_perf_coef'] in [0, None]:
                self.timer_15m += 1
                self.ability_json['home_perf_coef'] = 0
                self.ability_json['away_perf_coef'] = 0
                if (15 * 60) <= self.timer_15m < 30 * 60:
                    self.ability_json['home_perf_coef'] = -0.01
                    self.ability_json['away_perf_coef'] = -0.01

                elif self.timer_15m >= (30 * 60):
                    self.ability_json['home_perf_coef'] = -0.015
                    self.ability_json['away_perf_coef'] = -0.015
                    # print('\t2: Decrease level 2')
                    # print(f"\t\t Home Performance: {self.ability_json['home_perf_coef']} Away Performance: {self.ability_json['away_perf_coef']}")

            else:
                self.timer_15m = 0
                self.decrease_percent = 3

            # --------------------------------------------------------------------------------------------- #
            # Calculate the home/away expected ability:
            if len(self.ability_match) == 0 or (self.ability_json['period'] == 2 and
                                                self.ability_json['second'] <= 2 and
                                                self.ability_json['has_event'] is None):
                self.ability_json['home_p_in/de'], self.ability_json['home_perf_coef'] = 0, 0
                self.ability_json['away_p_in/de'], self.ability_json['away_perf_coef'] = 0, 0
                self.ability_json['home_exp_ability'] = self.ability_json['home_ability']
                self.ability_json['away_exp_ability'] = self.ability_json['away_ability']

            # ---------------------------------------------------------------------------------- #
            # DECREASE ABILITIES OF HOME AND AWAY TEAM WHEN THERE IS NO ATTACK DURING THE MATCH.
            elif len(self.ability_match) > 10:
                self.ability_json = self._decrease_both_ab(ability_json=self.ability_json, current_score=current_score)

            # ----------------------------------------------------------------------------------#
            # START TO CALCULATE THE EXPECTED ABILITIES OF BOTH TEAMS
            if self.ability_json['has_event'] is not None:
                self.ability_json['home_exp_ability'] = (1 + self.ability_json['home_p_in/de'] + self.ability_json['home_perf_coef']) * self.ability_json['home_ability']
                self.ability_json['away_exp_ability'] = (1 + self.ability_json['away_p_in/de'] + self.ability_json['away_perf_coef']) * self.ability_json['away_ability']
            elif self.ability_json['update'] == 'decreased_both':
                pass
            elif len(self.ability_match) == 0 or (self.ability_json['period'] == 2 and
                                                  self.ability_json['second'] <= 2 and
                                                  self.ability_json['has_event'] is None):
                pass
            else:
                self.ability_json['field'] = self.ability_match[-1]['field']
                self.ability_json['home_p_in/de'] = self._get_next_in_de_percent(home=True)
                self.ability_json['away_p_in/de'] = self._get_next_in_de_percent(home=False)

                if not (self.ability_json['home_perf_coef'] < 0 and self.ability_json['away_perf_coef'] < 0):
                    self.ability_json['home_perf_coef'] = self._get_next_perf_per(home=True)
                    self.ability_json['away_perf_coef'] = self._get_next_perf_per(home=False)

                self.ability_json['home_exp_ability'] = (1 + self.ability_json['home_p_in/de'] + self.ability_json['home_perf_coef']) * self.ability_json['home_ability']
                self.ability_json['away_exp_ability'] = (1 + self.ability_json['away_p_in/de'] + self.ability_json['away_perf_coef']) * self.ability_json['away_ability']

        except Exception as e:
            print(self.ability_json)
            raise e

        else:
            self.ability_match.append(self.ability_json)
            return self.ability_json


if __name__ == '__main__':
    # Call model
    # pickle_file_path = 'model/Germany_3rd_liga/ada_live_model.sav'
    pickle_file_path = 'model/Span_Primera_Ferderacion/ada_live_model.sav'
    with open(pickle_file_path, 'rb') as file:
        rf_model = pickle.load(file)

    # Json of match
    # file_name = 'json/Australia_league/73708288_FT.json'
    # file_name = 'json/Germany_3rd_liga/72775116_FT.json'
    file_name = 'json/Span_Primera_Ferderacion/73708288_FT.json'
    f = open(file_name)

    # returns JSON object as a dictionary
    api_json = json.load(f)

    # Create Live model
    live_model = LiveScore_Model(model=rf_model)

    # Create atk round list and ability of full match list
    current_atk_round = None
    full_ability = None
    for dict_sec in tqdm(api_json, desc="Starting to execute the api...."):
        ability = live_model.predict_expected_ability(input_api_json=dict_sec,
                                                      # attacking_round_list=current_atk_round,
                                                      # ability_fullmatch_list=full_ability
                                                      )

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
    final_filename = f"{os.path.split(file_name)[-1].split('.')[0]}.csv"
    full_ability_df[feat].to_csv(final_filename, index=False)
    print(f"Export file: {final_filename} completely")
    print(full_ability_df.shape)
    print(full_match_ab_df.shape)
