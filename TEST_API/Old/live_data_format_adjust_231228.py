import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pytz
import tzlocal
import os
import pathlib
from pprint import pprint


class Timer:
    def __init__(self):
        self.target_time = None

    def _get_utc_offset(self):
        # Get the time zone from the datetime object
        dt = datetime.now().replace(microsecond=0)
        current_timezone = dt.astimezone().tzinfo

        # Get the UTC offset as a timedelta
        utc_offset = current_timezone.utcoffset(dt)

        # Extract hours and minutes from the UTC offset timedelta
        offset_hours, _ = divmod(utc_offset.seconds // 60, 60)

        # Return the UTC offset as integers
        return offset_hours + 4

    def convert_target_time(self, target_time):
        # Get the utc offset
        utc_offset = self._get_utc_offset()

        # Convert datetime
        date_parts = target_time.split('.')
        date_format = "%Y-%m-%dT%H:%M:%S"
        self.target_time = datetime.strptime(date_parts[0], date_format) + timedelta(hours=utc_offset)
        return self.target_time

    def create_time_counter(self, event=None):
        current_time = datetime.now().replace(microsecond=0)

        # Update period
        event_code_id = event['eventCodeId']
        if event_code_id == 11:  # Start_1st_half
            self.target_time = self.convert_target_time(target_time=event['timestamp'])
            period = 1
            time_difference = 0
            min = 0
            sec = 0

        elif event_code_id == 1:  # Stop_1st_half
            period = 0
            time_difference = 2700
            min = None
            sec = None

        elif event_code_id == 12:  # Start_2nd_half
            self.target_time = self.convert_target_time(target_time=event['timestamp'])
            period = 1
            time_difference = 2700
            min = 45
            sec = 0

        elif event_code_id == 3:  # Stop_2nd_half
            period = 0
            time_difference = 9999
            min = None
            sec = None
        else:
            if event['in_game_period'] == 1:
                time_difference = int((current_time - self.target_time).total_seconds())
                period = 1
                min = time_difference // 60
                sec = time_difference % 60
            elif event['in_game_period'] == 2:
                time_difference = int((current_time - self.target_time).total_seconds()) + 2700
                period = 2
                min = time_difference // 60
                sec = time_difference % 60
            else:
                period = 0
                time_difference = 0
                min = 0
                sec = 0

        # Return In-game dictionary
        in_game_timer = {'in_game_period': period,
                         'in_game_timer': time_difference,
                         'min': min,
                         'sec': sec}

        return in_game_timer


class Engine:
    def __init__(self,
                 match_id,
                 event_code_ids,
                 selected_ids,
                 event_position: int = 0) -> None:
        # define url
        self.url_oddsfeed = 'http://210.57.28.64:22212/api/OddsFeed'
        self.url_feeddata = 'http://210.57.28.64:22212/api/FeedData'

        # initialize
        self.match_id = match_id
        self.event_position = event_position
        self.event_code_ids = event_code_ids
        self.selected_ids = selected_ids

        # both live match and past match
        self.feed_id = None
        self.feed_source = None
        self.match_event_info = []
        self.match_event_counter = []
        self.full_api_ls = []
        self.remove_id = [2100, 1076, 228, 1073, 2097, 207]
        self.rb_code_ls = [int(i) for i in self.selected_ids.keys() if int(i) not in self.remove_id]

        # LIVE MATCH
        # build Timer to calculate
        self.Timer = Timer()
        self.full_rb_events = []
        self.event_data_ft = None
        self.event_data_ht = None

        # get feed info
        self.GetFeedInfo()

    # ------------------ FUNCTION TO GET FEED IFO----------------------
    def GetFeedInfo(self):
        url = self.url_feeddata + '/GetFeedMappingInfo?matchId=' + str(self.match_id)
        response = requests.get(url)
        data = response.json()
        self.feed_id = data['feedId']
        self.feed_source = data['feedSource']
        # self.feed_reverse = data['feedReverse']

    # ------------------ FUNCTION TO CREATE TIMER FOR PAST MATCH----------------------
    def _create_timer(self):
        # period 1
        period_1 = {'in_game_timer': [i for i in range(0, 3600)],
                    'min': [i // 60 for i in range(0, 3600)],
                    'sec': [i % 60 for i in range(0, 3600)],
                    'in_game_period': [1 for i in range(0, 3600)]}
        period_1_df = pd.DataFrame.from_dict(period_1, orient='columns')

        # period 2
        period_2 = {'in_game_timer': [i for i in range(2700, 6000)],
                    'min': [i // 60 for i in range(2700, 6000)],
                    'sec': [i % 60 for i in range(2700, 6000)],
                    'in_game_period': [2 for i in range(2700, 6000)]}
        period_2_df = pd.DataFrame.from_dict(period_2, orient='columns')

        # Full match
        df_time = (
            pd.concat([period_1_df, period_2_df]).sort_values(by=['in_game_period', 'min']).reset_index(drop=True)[
                ['in_game_period', 'in_game_timer', 'min', 'sec']])
        timer = df_time.to_dict(orient='records')

        return timer

    # ------------------ FUNCTION TO STRUCTURE THE ADMIN DATA ----------------------
    def get_AB_timer_metadata(self, isFT=True, is_live: bool = True):
        url = self.url_oddsfeed + f'/GetLiveMatchAbility?isFT={isFT}&matchId={self.match_id}'
        response = requests.get(url)
        js_admin = response.json()

        # -- get initial abilities --
        if is_live:
            Ability = {"Home": js_admin["ability"]["home"],
                       "Away": js_admin["ability"]["away"]}
        else:
            Ability = {"Home": js_admin["initAbility"]["home"],
                       "Away": js_admin["initAbility"]["away"]}

        # -- get metadata of match --
        Match = {"MatchTime": 90,
                 "LeagueId": js_admin["matchLeague"]["leagueId"],
                 "MatchID": js_admin["matchLeague"]["matchId"],
                 "HomeTeamId": js_admin["matchLeague"]["homeId"],
                 "AwayTeamId": js_admin["matchLeague"]["awayId"]}

        # -- TIMER --

        # Get the utc offset
        # utc_offset = self._get_utc_offset(dt=current_time)

        # target_time = match_details['kickOffTime']
        # date_parts = target_time.split('.')
        # date_format = "%Y-%m-%dT%H:%M:%S"
        # target_time = datetime.strptime(date_parts[0], date_format) + timedelta(hours=utc_offset)

        # Get starting time
        match_details = js_admin['matchLeague']
        target_time = self.Timer.convert_target_time(match_details['kickOffTime'])

        # Get the current time
        current_time = datetime.now()

        # Calculate the time difference
        time_difference = current_time - target_time

        # calculate in-game time
        ig_seconds = time_difference.total_seconds()

        # check if game is 2nd half, add 45 mins
        if match_details['livePeriod'] == 2:
            ig_seconds += 2700

        # check if HT then keep ig_seconds constant
        if match_details['isHT']:
            ig_seconds = 2700

        # Determine the local time zone
        local_tz = str(tzlocal.get_localzone())

        # add timezone into datetime objet
        obj_tz = pytz.timezone(local_tz).localize(target_time)
        kick_off_time = obj_tz.strftime("%Y-%m-%dT%H:%M:%S %z")

        Timer = {'KickoffTime': kick_off_time,
                 "LiveTimer": int(ig_seconds),
                 'min': int(ig_seconds // 60),
                 'sec': int(ig_seconds % 60),
                 "LivePeriod": js_admin["matchLeague"]["livePeriod"],
                 'isRunning': True if js_admin["matchLeague"]['eventStatus'] == 'running' else False}

        # Create a new dictionary with the desired structure
        final_data = {'Ability': Ability,
                      'Match': Match,
                      'Timer': Timer}

        return js_admin, final_data

    # ------------------ FUNCTION TO GET RUNNING BALL EVENT ----------------------
    def get_rb_events(self):
        body = {'sportTickerId': self.feed_id,
                'feedSource': self.feed_source,
                'lastEventNumber': self.event_position,
                'eventCodeIdList': []}

        header = {'content-type': 'application/json', 'accept': 'text/plain'}
        s_url = self.url_feeddata + '/GetFeedEvents'
        response = requests.post(url=s_url, json=body, headers=header)

        # convert into json
        js_rb = response.json()
        return js_rb

    # ------------------ SAVE LOF FILE OF MATCH  ----------------------
    def save_json(self, is_live_match: bool, file_directory='api_folder/'):

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
                print(
                    f"Directory '{dir_path}' already exists. Starting to execute log file and add into the corresponding directory.")

        # Check directory input
        file_directory = os.path.join(file_directory, str(self.match_id))
        create_directory(dir_path=file_directory)
        # Save into json file
        # Specify the file name where you want to save the JSON data
        if is_live_match:
            json_file_name = f'live_match_api_{self.match_id}.json'
            event_info = self.full_rb_events
            event_name = 'live_match_event_info.json'

        else:
            json_file_name = f'past_match_api_{self.match_id}.json'
            event_info = self.match_event_info
            event_name = 'past_match_event_info.json'

        self.full_path = [os.path.join(file_directory, json_file_name),
                         os.path.join(file_directory, event_name)]

        # Save the dictionary to a JSON file API and Event info
        with open(self.full_path[0], 'w') as json_api_file:
            json.dump(self.full_api_ls, json_api_file, indent=4)

        with open(self.full_path[1], 'w') as json_info_file:
            json.dump(event_info, json_info_file, indent=4)
        print(f'\nDictionary saved to:\n{self.full_path[0]}\n{self.full_path[1]}')

    # ------------------ FUNCTION TO CALL API FOR PAST MATCH ----------------------
    def get_logs_for_past_match(self, isFT: bool):
        # --- CREATE ADMIN DATA ---
        js_admin, admin_data = self.get_AB_timer_metadata(isFT=isFT,is_live=False)

        # --- Get Running ball event ---
        js_rb = self.get_rb_events()

        # --- Create the event counter ---
        event_counter = {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}

        # define some code should be eliminated
        atk_h = [1024, 1075]
        atk_a = [2048, 2099]

        safe_h = [1051, 1074]
        safe_a = [2075, 2098]

        dan_h = [1052, 1076]
        dan_a = [2076, 2100]

        # define some code should be eliminated
        focus = [1024, 2048, 1052, 2076, 1051, 2075]
        remove = [1075, 2099, 1074, 2098, 1076, 2100]

        for i, event in enumerate(js_rb):
            event_dict = {key: event[key] for key in ['eventNumber', 'eventCodeId', 'homeScore', 'awayScore',
                                                      'sportsTickerStateId', 'min', 'sec', 'eventCode_Desc']}
            event_code_id = event_dict['eventCodeId']
            # --- Remove duplicated events ---
            # Get previous event:
            if i == 0:
                previous_event = event_dict
            else:
                previous_event = js_rb[i - 1]

            # Remove consecutive event based on 'eventCodeId'
            filter_1 = (event_code_id in remove) and ((previous_event['eventCodeId'] in focus) or (previous_event['eventCodeId'] in remove))
            #filter_2 =

            # Change period state:
            if event_dict['sportsTickerStateId'] == 2:
                event_dict['in_game_period'] = 1
            elif event_dict['sportsTickerStateId'] == 8:
                event_dict['in_game_period'] = 2
            else:
                if event_dict['eventCode_Desc'] == 'Stop 1st half':
                    event_dict['in_game_period'] = 1
                elif event_dict['eventCode_Desc'] == 'Stop 2nd half':
                    event_dict['in_game_period'] = 2
                else:
                    event_dict['in_game_period'] = 0

            # remove sportsTickerStateId:
            event_dict.pop('sportsTickerStateId', None)

            # calculate in-game timer
            event_dict['in_game_timer'] = event_dict['min'] * 60 + event_dict['sec']

            # Reduce the event duplication 
            if any([filter_1]):
                pass
            else:
                if event_code_id in atk_h:
                    event_code_id = atk_h[0]
                elif event_code_id in atk_a:
                    event_code_id = atk_a[0]
                elif event_code_id in safe_h:
                    event_code_id = safe_h[0]
                elif event_code_id in safe_a:
                    event_code_id = safe_a[0]

                # remove some code and top-up the event_counter
                if event_code_id in self.rb_code_ls:
                    event_counter[self.selected_ids[str(event_code_id)]['code']] += 1
                    # print(self.selected_ids[str(event_code_id)]['code'], event_counter[self.selected_ids[str(event_code_id)]['code']])
                    event_counter_copy = event_counter.copy()
                    self.match_event_counter.append(event_counter_copy)
                    self.match_event_info.append(event_dict)

        # ---------------- Create Timer to integrate with event counter: ----------------
        # create timer
        timer = self._create_timer()
        timer_df = pd.DataFrame(timer)

        # create event info df:
        event_df = pd.DataFrame(data=self.match_event_info).reset_index().rename(columns={'index': 'key'})

        # merge both of them
        test = pd.merge(left=timer_df, right=event_df, on=['in_game_period', 'in_game_timer', 'min', 'sec'], how='left')
        test = test.ffill()

        # Get the last index of the event df
        last_ig_index = test[test['eventCodeId'] == 3].index[1]
        full_match = test.iloc[:last_ig_index, :].dropna().reset_index(drop=True)

        # Create the final output:
        for i, igp, igt, m, s, k in full_match[['in_game_period', 'in_game_timer', 'min', 'sec', 'key']].itertuples(index=True):
            try:
                k_ = int(k)
            except ValueError:
                print(i, igp, igt, m, s, k)
                pass
            else:
                if i == 0:
                    final_output = {'ingame_Timer': {'in_game_period': igp, 'in_game_timer': igt, 'min': m, 'sec': s},
                                    'Event': self.match_event_counter[k_],
                                    'LastEvent': {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}}
                else:
                    final_output = {'ingame_Timer': {'in_game_period': igp, 'in_game_timer': igt, 'min': m, 'sec': s},
                                    'Event': self.match_event_counter[k_],
                                    'LastEvent': self.full_api_ls[-1]['Event']}

                final = final_output.copy()
                final.update(admin_data)
                self.full_api_ls.append(final)

        # Final return the api full match
        print(f">>>>>> Finish fetching data of match id: {self.match_id}")
        return self.full_api_ls

    #  ------------------ GET API FOR LIVE MATCH ----------------------
    def get_logs_for_current_match(self, isFT: bool = True):

        # --- FUNCTION ---
        def get_keys(dictionary, keys: list):
            return {key: dictionary[key] for key in keys}

        # --- CREATE ADMIN DATA ---
        js_admin, admin_data = self.get_AB_timer_metadata(isFT=isFT, is_live=True)

        # --- Create the event counter ---
        if isFT:
            if len(self.full_api_ls) > 0:
                event_counter = self.full_api_ls[-1]['Event']
            else:
                event_counter = {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}
        else:
            if len(self.full_api_ls) > 0:
                event_counter = self.event_data_ht['Event']
            else:
                event_counter = {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}

        # --- Get Running ball event ---
        current_position = self.event_position  # Start from 0 and gradually increase until the end
        js_rb = self.get_rb_events()
        # format js_rb
        selected_keys = ['eventNumber', 'eventCodeId', 'homeScore', 'awayScore',
                         'sportsTickerStateId', 'timestamp','min', 'sec', 'eventCode_Desc']
        js_rb = [get_keys(dictionary=e_dict, keys=selected_keys) for e_dict in js_rb]
        # print("Event list")
        # pprint(js_rb)

        # Get last event
        if len(self.full_api_ls) > 0:
            last_event_counter = self.full_api_ls[-1]['Event']
        else:
            last_event_counter = {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}

        # define some code should be eliminated
        focus = [1024, 2048, 1052, 2076, 1051, 2075]
        remove = [1075, 2099, 1074, 2098, 1076, 2100]

        # Don't start the game
        #print('by each time:', len(js_rb), 'Full match', len(self.full_rb_events))

        if len(js_rb) == 0 and len(self.full_rb_events) == 0:
            rb_data = {
                'ingame_Timer': {'in_game_period': 0,
                                 'in_game_timer': 0,
                                 'min': 0,
                                 'sec': 0},
                'Event': event_counter,
                'LastEvent': last_event_counter}

        # Start the game but there are not updated events
        elif len(js_rb) == 0 and len(self.full_rb_events) > 0:
            # check timer
            previous_event = self.full_rb_events[-1]

            # determine time counter
            in_game_timer = self.Timer.create_time_counter(event=previous_event)

            # create final output
            rb_data = {
                'ingame_Timer': in_game_timer,
                'Event': event_counter,
                'LastEvent': last_event_counter}
        else:
            # loop the js_rb to get events
            for i, event in enumerate(js_rb):
                # pprint(event)

                # Update event position
                current_position = event['eventNumber']

                # --- Preprocess rb event ------
                event_code_id = event['eventCodeId']
                # Change period state:
                if event['sportsTickerStateId'] == 2:
                    event['in_game_period'] = 1
                elif event['sportsTickerStateId'] == 8:
                    event['in_game_period'] = 2
                else:
                    if event['eventCode_Desc'] == 'Stop 1st half':
                        event['in_game_period'] = 1
                    elif event['eventCode_Desc'] == 'Stop 2nd half':
                        event['in_game_period'] = 2
                    else:
                        event['in_game_period'] = 0
                # remove sportsTickerStateId:
                event.pop('sportsTickerStateId', None)
                # calculate in-game timer
                event['in_game_timer'] = event['min'] * 60 + event['sec']

                # Case 1: there is the rb event, but it is not in-game event (Period 1) => keep counter
                if event['in_game_period'] == 0:

                    # append rb_event into a full list
                    self.full_rb_events.append(event)

                    # Determine timer
                    in_game_timer = self.Timer.create_time_counter(event=event)

                    # Update counter
                    rb_data = {
                        'ingame_Timer': in_game_timer,
                        'Event': event_counter,
                        'LastEvent': last_event_counter}
                else:
                    # --- Remove duplicated events ---
                    # Get previous event:
                    if i == 0:
                        previous_event = self.full_rb_events[-1]
                    else:
                        previous_event = js_rb[i - 1]
                    #  Check if the current event and previous event have the same purpose based on 'eventCodeId'
                    filter_1 = (event_code_id in remove) and ((previous_event['eventCodeId'] in focus)
                                                              or (previous_event['eventCodeId'] in remove))

                    # Remove the consecutive event
                    if filter_1:
                        # append rb_event into a full list
                        self.full_rb_events.append(event)
                        # Determine timer
                        in_game_timer = self.Timer.create_time_counter(event=event)
                        # Update counter
                        rb_data = {
                            'ingame_Timer': in_game_timer,
                            'Event': event_counter,
                            'LastEvent': last_event_counter
                        }

                    else:
                        # top-up the event_counter
                        if event_code_id in self.rb_code_ls:
                            event_counter[self.selected_ids[str(event_code_id)]['code']] += 1
                            event_counter_copy = event_counter.copy()

                            # append rb_event into a full list
                            self.full_rb_events.append(event)

                            # Determine timer
                            in_game_timer = self.Timer.create_time_counter(event=event)

                            # Update counter
                            rb_data = {
                                'ingame_Timer': in_game_timer,
                                'Event': event_counter_copy,
                                'LastEvent': last_event_counter
                            }

                        else:
                            # determine time counter
                            in_game_timer = self.Timer.create_time_counter(event=event)

                            # create final output
                            rb_data = {
                                'ingame_Timer': in_game_timer,
                                'Event': event_counter,
                                'LastEvent': last_event_counter
                            }

        # ------------------- Update data -----------------------
        # Merge rb_data with admin_data
        admin_data.update(rb_data)
        self.event_position = current_position

        # self.event_data_ft = admin_data
        # Final return the api full match
        #print(len(js_rb),'\n\n', js_rb)
        # Game is still running
        self.is_running = admin_data['Timer']['isRunning']
        if self.is_running: #len(js_rb) > 0 and len(self.full_api_ls) == 0 or len(self.full_api_ls) > 0:
            self.full_api_ls.append(admin_data)

        elif len(self.full_api_ls) > 8:
            print(f">>>>>> Finish fetching data of match id: {self.match_id}")
            return admin_data
        else:
            return None


if __name__ == '__main__':
    match_id_ = 77854937 #78228478  # 78092138 #78041432  # 77994064 #78041654 #78041657 #78041654 #77304851  # 77926259  # 77623787 #77592032
    event_code_ids = []
    position = 0

    json_file_path = r'D:\TRI LE\GOAL_LIVE_PREDATOR\TEST_API\rb_code_upd.json'
    # Open the file and load the JSON data
    with open(json_file_path, 'r') as json_file:
        rb_code = json.load(json_file)

    match = Engine(match_id=match_id_,
                   event_code_ids=event_code_ids,
                   selected_ids=rb_code,
                   event_position=position)

    js_adm, final_output = match.get_AB_timer_metadata(isFT=True)

    # get rb event
    # rb_data = match.get_rb_events()
    # pprint(rb_data)
    # pprint(final_output)

    # # TEST PAST MATCH
    # log_api = match.get_logs_for_past_match(isFT=True)

    # TEST LIVE MATCH
    is_running = True
    #while is_running:
    for i in range(5):
        log_api = match.get_logs_for_current_match(isFT=True)
        js_adm, final_output = match.get_AB_timer_metadata(isFT=True)
        if log_api is not None:

            print('\n\n Live Timer:')
            pprint(log_api['Timer'])
            try:
                print('\n\n In game Timer:')
                pprint(log_api['ingame_Timer'])
            except KeyError:
                print(log_api)
                break
            finally:
                is_running = log_api['Timer']['isRunning']
        else:
            print(f'Game has been not started yet, It still remains {final_output["Timer"]["min"]} mins and {final_output["Timer"]["sec"]} secs before staring games')

    match.save_json(is_live_match=False, file_directory='api_folder')
    # pprint(match.full_rb_events)
