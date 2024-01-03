import re
import json
import pandas as pd
import pickle

# Create model:
pickle_file_path = 'model/rf_model.sav'
with open(pickle_file_path, 'rb') as file:
    rf_proba_model = pickle.load(file)

def calculate_attacking_round(data: list):
    test = pd.DataFrame(data)

    # count rows of home/away
    home_count = (test['field'] == 'home').sum()
    away_count = (test['field'] == 'away').sum()

    # Determine that this round is the counter attack or normal attack or nothing happen
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
        one_attacking_round = pd.pivot_table(data=one_round, values='sec', columns='type', index='field',
                                             aggfunc='count', fill_value=0)
    elif home_count < away_count:
        one_round = test[test['field'] == 'away'].reset_index(drop=True)
        one_attacking_round = pd.pivot_table(data=one_round, values='sec', columns='type', index='field',
                                             aggfunc='count', fill_value=0)

    # Case the away's event == home's event => there is no values which determine the event belonging to what team.
    else:
        one_round = test[test['field'] == 'home'].reset_index(drop=True)
        one_attacking_round = pd.pivot_table(data=one_round, values='sec', columns='type', index='field',
                                             aggfunc='count', fill_value=0)

    # Drop down level of multi index
    one_attacking_round.columns = list(one_attacking_round.columns)
    one_attacking_round = one_attacking_round.reset_index()

    ### COUNTER ATTACK ###
    one_attacking_round['couter_attack'] = counter

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


def predict_percent(atk_round: list, model):
    # Transform to 1 attacking round from here to apply in model
    atk_df = calculate_attacking_round(atk_round)

    # Reorder columns
    stop_index = list(atk_df.columns).index('couter_attack')
    columns_order = ['period', 'start_sec', 'duration', 'field', 'couter_attack']
    columns_order.extend(list(atk_df.columns)[1:stop_index])

    # Determine the features:
    sample = atk_df.rename(columns={'DAN': 'Danger'})
    features = ['couter_attack', 'CR', 'AT', 'DAT', 'Danger', 'DFK', 'PEN']
    for feat in features:
        if feat not in sample.columns:
            sample[feat] = 0
    sample = sample[features]

    # Apply model to predict:
    label = model.predict(sample)[0]

    # get percent:
    mapping = {'Low': 0.1, 'Medium': 0.2, 'High': 0.3}
    return mapping[label]


attacking_round = []
full_match = []
full_event = []
ability_match = list()
f = open('json/matches_api.json')

# returns JSON object as
# a dictionary
api_json = json.load(f)

for dict_sec in api_json:
    # Timer:
    timer = dict_sec['Timer']

    # CURRENT EVENT
    home_current = {k: v for k, v in dict_sec['Event'].items() if '1' in k}
    away_current = {k: v for k, v in dict_sec['Event'].items() if '2' in k}

    # LAST EVENT
    home_previous = {k: v for k, v in dict_sec['LastEvent'].items() if '1' in k}
    away_previous = {k: v for k, v in dict_sec['LastEvent'].items() if '2' in k}

    # Ability of home and away:
    home_ability = dict_sec['Ability']['Home']
    away_ability = dict_sec['Ability']['Away']

    # prediction ability
    ability_json = {'period': timer['LivePeriod'],
                    'second': timer['LiveTimer'],
                    'has_event': None,
                    'update': None,
                    'home_percent_increase': None,
                    'away_percent_increase': None,
                    'home_ability': home_ability,
                    'home_exp_ability': None,
                    'away_ability': away_ability,
                    'away_exp_ability': None
                    }

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
            ability_json['has_event'] = event_dict['type']
            full_event.append(event_dict)
            # print(event_dict)
            print(ability_json)

            # If type is Safe => Stop increasing the ability then back to Taiwan ability.
            if (event_dict['type'] == 'SAFE') or (event_dict['sec'] < 2):
                # print(f"Period: {event_dict['period']}, Running Second: {event_dict['sec']}")
                # print(f'FIELD: {event_dict["field"]} STOPPPPP!!')
                # print('\n\n')
                # Start a attacking round
                if len(attacking_round) == 0:
                    attacking_round.append(event_dict)

                # IF the field is different in next event and type as SAFE or start new period => the oppenent steals a ball => Reset the attacking round for opponent/Rival
                elif (event_dict['field'] != attacking_round[-1]['field']) or (
                        event_dict['period'] != attacking_round[-1]['period']):
                    full_match.append(attacking_round)
                    attacking_round = list()
                    attacking_round.append(event_dict)

                # IF the field is same in next event and type as SAFE, the team go back their field to implement new round. => Still count in one attacking round
                elif event_dict['field'] == attacking_round[-1]['field']:
                    attacking_round.append(event_dict)

                # percent of ability go back 0
                ability_json['home_percent_increase'] = 0
                ability_json['away_percent_increase'] = 0


            # Check the next event, if event is same field, => add that event to the current round:
            elif event_dict['field'] == attacking_round[-1]['field']:
                attacking_round.append(event_dict)

                # Trigger model:
                if (event_dict['type'] in ['DAT', 'DAN', 'DFK']) and (
                        attacking_round[-2]['type'] in ['DAT', 'DAN', 'DFK']):

                    # Transform to 1 attacking round from here to apply in model
                    get_percent = predict_percent(atk_round=attacking_round, model=rf_proba_model)

                    # update the ability
                    ability_json['update'] = True
                    if event_dict['field'] == 'home':
                        ability_json['home_percent_increase'] = get_percent
                        ability_json['away_percent_increase'] = 0
                    else:
                        ability_json['home_percent_increase'] = 0
                        ability_json['away_percent_increase'] = get_percent
                else:
                    ability_json['home_percent_increase'] = ability_match[-1]['home_percent_increase']
                    ability_json['away_percent_increase'] = ability_match[-1]['away_percent_increase']

            # In case as counterstrike, still add to that current round but this is rival's attacking round.
            elif event_dict['field'] != attacking_round[-1]['field'] and event_dict['type'] not in ['TI', 'CR']:
                # if team is attacking. Then next event is attack of the opponent => Start new attacking round.
                if attacking_round[-1]['type'] in ['AT', 'DAT', 'DAN'] and event_dict['type'] in ['FK', 'AT']:
                    full_match.append(attacking_round)
                    attacking_round = list()
                    attacking_round.append(event_dict)
                else:
                    attacking_round.append(event_dict)

                ability_json['home_percent_increase'] = ability_match[-1]['home_percent_increase']
                ability_json['away_percent_increase'] = ability_match[-1]['away_percent_increase']


            # Different field but type Throw in => the opponent get the ball
            elif event_dict['field'] != attacking_round[-1]['field'] and event_dict['type'] in ['TI']:
                ability_json['home_percent_increase'] = ability_match[-1]['home_percent_increase']
                ability_json['away_percent_increase'] = ability_match[-1]['away_percent_increase']
            else:
                raise Exception('There is error in there')
            # print(event_dict)
        else:
            if len(ability_json) == 0:
                is_event = False
                update = False

    # Calculate the home/away expected ability:
    if len(ability_match) == 0:
        ability_json['home_percent_increase'] = 0
        ability_json['away_percent_increase'] = 0
        ability_json['home_exp_ability'] = ability_json['home_ability']
        ability_json['away_exp_ability'] = ability_json['away_ability']
    else:
        if ability_json['has_event'] is not None:
            ability_json['home_exp_ability'] = (1 + ability_json['home_percent_increase']) * ability_json[
                'home_ability']
            ability_json['away_exp_ability'] = (1 + ability_json['away_percent_increase']) * ability_json[
                'away_ability']
        else:
            ability_json['home_percent_increase'] = ability_match[-1]['home_percent_increase']
            ability_json['away_percent_increase'] = ability_match[-1]['away_percent_increase']
            ability_json['home_exp_ability'] = (1 + ability_json['home_percent_increase']) * ability_json[
                'home_ability']
            ability_json['away_exp_ability'] = (1 + ability_json['away_percent_increase']) * ability_json[
                'away_ability']
    ability_match.append(ability_json)