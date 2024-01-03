import pandas as pd


def from_event_to_ATK_round(df_event):
    feat_attack_round = ['period', 'minutes', 'seconds', 'field', 'type', 'goal_ability']
    full_match_list = []
    attacking_round_list = []

    for idx, p, min, sec, f, tp, ga in df_event[feat_attack_round].itertuples():

        # If the event is Safe => Start to an attacking round or have likelihood of counter-attack from the opponent
        if (f in ['home', 'away']) & (tp == 'Safe'):
            dict_atk = {'index': idx, 'period': p, 'min': min, 'sec': sec, 'field': f, 'type': tp, 'goal_ability': ga}

            # Start a attacking round
            if len(attacking_round_list) == 0:
                attacking_round_list.append(dict_atk)

            # IF the field is different in next event and type as SAFE => the oppenent steals a ball => Reset the attacking round for opponent/Rival
            elif f != attacking_round_list[-1]['field']:
                full_match_list.append(attacking_round_list)
                attacking_round_list = list()
                attacking_round_list.append(dict_atk)

            # IF the field is same in next event and type as SAFE, the team go back their field to implement new round. => Still count in one attacking round
            elif f == attacking_round_list[-1]['field']:
                attacking_round_list.append(dict_atk)

        # Check the next event, if event is same field, => add that event to the current round:
        elif f == attacking_round_list[-1]['field']:
            dict_atk = {'index': idx, 'period': p, 'min': min, 'sec': sec, 'field': f, 'type': tp, 'goal_ability': ga}
            attacking_round_list.append(dict_atk)

        # In case as counterstrike, still add to that current round but this is rival's attacking round.
        elif f != attacking_round_list[-1]['field'] and tp not in ['Safe', 'TI']:
            dict_atk = {'index': idx, 'period': p, 'min': min, 'sec': sec, 'field': f, 'type': tp, 'goal_ability': ga}
            attacking_round_list.append(dict_atk)

        # Different field but type Throw in => the opponent get the ball
        elif f != attacking_round_list[-1]['field'] and tp == 'TI':
            pass
        else:
            break

    # for the last one
    full_match_list.append(attacking_round_list)
    return full_match_list


def calculate_attacking_round(data: list):
    test = pd.DataFrame(data)

    # count rows of home/away
    home_count = (test['field'] == 'home').sum()
    away_count = (test['field'] == 'away').sum()

    # Determine that this round is the counter attack or normal attack or nothing happen
    first_event = test.iloc[0][['field', 'type']].to_dict()
    last_event = test.iloc[-1][['field', 'type']].to_dict()
    if (first_event['field'] != last_event['field']) and (first_event['type'] == 'Safe') and (
            home_count > 0 and away_count > 0) and test.shape[0] > 2:
        counter = True
    else:
        counter = False

        ### IF HOME COUNT > AWAY COUNT => THIS IS THE ATTACKING ROUND OF HOME, OTHEWISE ###
    if home_count > away_count:
        one_round = test[test['field'] == 'home'].reset_index(drop=True)
        one_attacking_round = pd.pivot_table(data=one_round, values='index', columns='type', index='field',
                                             aggfunc='count', fill_value=0)
    elif home_count < away_count:
        one_round = test[test['field'] == 'away'].reset_index(drop=True)
        one_attacking_round = pd.pivot_table(data=one_round, values='index', columns='type', index='field',
                                             aggfunc='count', fill_value=0)

    # Case the away's event == home's event => there is no values which determine the event belonging to what team.
    else:
        one_round = test[test['field'] == 'home'].reset_index(drop=True)
        one_attacking_round = pd.pivot_table(data=one_round, values='index', columns='type', index='field',
                                             aggfunc='count', fill_value=0)

    # Drop down level of multi index
    one_attacking_round.columns = list(one_attacking_round.columns)
    one_attacking_round = one_attacking_round.reset_index()

    ### TO CALCULATE THE DIFFERENCE OF GOAL ABILITY ###
    column_name = 'goal_ability'
    # Calculate the difference between the first and last row in the specified column
    first_row_value = one_round.at[0, column_name]
    last_row_value = one_round.at[one_round.index[-1], column_name]
    goal_ability = last_row_value - first_row_value
    one_attacking_round['goal_ability'] = goal_ability

    ### COUNTER ATTACK ###
    one_attacking_round['couter_attack'] = counter

    ### CACULATE THE ATTTACKING DURATION AND START TIME ###
    column_name = ['period', 'min', 'sec']
    # Calculate the difference between the first and last row for min and sec
    first_row = test.iloc[0][column_name]
    last_row = test.iloc[-1][column_name]
    # Calculate the period of a attacking round
    duration = (last_row['min'] - first_row['min']) * 60 + (last_row['sec'] - first_row['sec'])
    # Add this value in this attacking round
    one_attacking_round['duration'] = duration
    # set start min and start sec
    one_attacking_round['period'] = first_row['period']
    one_attacking_round['start_min'] = first_row['min']
    one_attacking_round['start_sec'] = first_row['sec']

    return one_attacking_round


def transform_df(match_id):
    # Filter the match id
    test_features = sum_event_matches[(sum_event_matches['match_id'] == match_id)].sort_values(
        by=['match_time', 'match_id', 'period', 'minutes', 'seconds']).reset_index(drop=True)
    # Print some info of shape
    print('Total event of goal ability:', test_features[test_features['goal_ability'] != 0].shape)
    print('Total event in this match:', test_features.shape)

    # Get meta data of a match
    meta_data_match = test_features[['match_id', 'match_time', 'ibc_id', 'field']].drop_duplicates()

    # Filter on event to transform
    filter_round = (~test_features['type'].isin(['not_event'])) & (test_features['field'].isin(['home', 'away']))
    only_event = test_features[filter_round].drop(columns=['match_id', 'match_time', 'ibc_id']).reset_index(drop=True)

    # Get the attacking round from the match => a list containing all event is am attacking round
    full_match_list = from_event_to_ATK_round(df_event=only_event)

    # From list of event dictionary retuning to the Dataframe
    at_rd_list = [calculate_attacking_round(round) for round in full_match_list]
    full_round_match = pd.concat(at_rd_list).reset_index(drop=True).fillna(0)

    # Get specific features
    feat = ['period', 'start_min', 'start_sec', 'duration', 'couter_attack', 'field', 'Safe', 'TI', 'GK', 'CR', 'Foul',
            'AT', 'DAT', 'Danger', 'FK', 'DFK', 'PEN', 'goal_ability']
    full_round_match = full_round_match[feat]

    # Merge full_round_match with meta data match
    atk_round_match = pd.merge(left=meta_data_match, right=full_round_match, on='field', how='left')

    return atk_round_match


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


def determine_when_attacking(event_dictionary,
                            ability_dictionary,
                            ability_match,
                            attacking_round_list,
                            full_match_list,
                            model):
    if (event_dictionary['type'] == 'SAFE') or (event_dictionary['sec'] < 2):
        if len(attacking_round_list) == 0:
            attacking_round_list.append(event_dictionary)

        # IF the field is different in next event and type as SAFE or start new period => the oppenent steals a ball => Reset the attacking round for opponent/Rival
        elif (event_dictionary['field'] != attacking_round_list[-1]['field']) or (
                event_dictionary['period'] != attacking_round_list[-1]['period']):
            full_match_list.append(attacking_round_list)
            attacking_round_list = list()
            attacking_round_list.append(event_dictionary)

        # IF the field is same in next event and type as SAFE, the team go back their field to implement new round. => Still count in one attacking round
        elif event_dictionary['field'] == attacking_round_list[-1]['field']:
            attacking_round_list.append(event_dictionary)

        # percent of ability go back 0
        ability_dictionary['home_percent_increase'] = 0
        ability_dictionary['away_percent_increase'] = 0

        # Check the next event, if event is same field, => add that event to the current round:
    elif event_dictionary['field'] == attacking_round_list[-1]['field']:
        attacking_round_list.append(event_dictionary)

        # Trigger model:
        if (event_dictionary['type'] in ['DAT', 'DAN', 'DFK']) and (attacking_round_list[-2]['type'] in ['DAT', 'DAN', 'DFK']):

            # Transform to 1 attacking round from here to apply in model
            get_percent = predict_percent(atk_round=attacking_round_list,
                                          model=model)

            # update the ability
            ability_dictionary['update'] = True
            if event_dictionary['field'] == 'home':
                ability_dictionary['home_percent_increase'] = get_percent
                ability_dictionary['away_percent_increase'] = 0
            else:
                ability_dictionary['home_percent_increase'] = 0
                ability_dictionary['away_percent_increase'] = get_percent
        else:
            ability_dictionary['home_percent_increase'] = ability_match[-1]['home_percent_increase']
            ability_dictionary['away_percent_increase'] = ability_match[-1]['away_percent_increase']

        # In case as counterstrike, still add to that current round but this is rival's attacking round.
    elif event_dictionary['field'] != attacking_round_list[-1]['field'] and event_dictionary['type'] not in ['TI',
                                                                                                             'CR']:
        # if team is attacking. Then next event is attack of the opponent => Start new attacking round.
        if attacking_round_list[-1]['type'] in ['AT', 'DAT', 'DAN'] and event_dictionary['type'] in ['FK', 'AT']:
            full_match_list.append(attacking_round_list)
            attacking_round_list = list()
            attacking_round_list.append(event_dictionary)
        else:
            attacking_round_list.append(event_dictionary)

        ability_dictionary['home_percent_increase'] = ability_match[-1]['home_percent_increase']
        ability_dictionary['away_percent_increase'] = ability_match[-1]['away_percent_increase']

        # Different field but type Throw in => the opponent get the ball
    elif event_dictionary['field'] != attacking_round_list[-1]['field'] and event_dictionary['type'] in ['TI']:
        ability_dictionary['home_percent_increase'] = ability_match[-1]['home_percent_increase']
        ability_dictionary['away_percent_increase'] = ability_match[-1]['away_percent_increase']
    else:
        raise Exception('There is error in there')
