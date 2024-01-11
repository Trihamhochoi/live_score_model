# -------------- IMPORT NECESSARY PACKAGES -------------- #
import math
# from live_timer import Timer
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
import getpass
import logging
import copy


# -------------- DEFINE LIVE TIMER --------------#
class Timer:
    def __init__(self):
        self.target_time = None
        self.period = 0  # Update again

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

    def convert_target_time(self, target_time: str):
        # Get the utc offset
        utc_offset = self._get_utc_offset()

        # Convert datetime
        date_parts = target_time.split('.')
        date_format = "%Y-%m-%dT%H:%M:%S"
        target_time_convert = datetime.strptime(date_parts[0], date_format) + timedelta(hours=utc_offset)
        return target_time_convert

    def create_time_counter(self, event_code_id=None):
        current_time = datetime.now()
        # print("current time:", current_time)
        time_difference = None

        # UPDATE PERIOD AND KICK-OFF TIME
        if event_code_id is not None:
            # Start_1st_half
            if event_code_id in [10, 11]:
                # Calculate the kick-off time
                self.target_time = current_time
                self.period = 1
                time_difference = int((current_time - self.target_time).total_seconds())
                min_ = time_difference // 60
                sec_ = time_difference % 60
                in_game_timer = {'in_game_period': 1,
                                 'in_game_timer': time_difference,
                                 'min': min_,
                                 'sec': sec_}

                return in_game_timer

            # Stop_1st_half
            elif event_code_id == 1:
                self.period = 11
                time_difference = 2700
                min_ = time_difference // 60
                sec_ = time_difference % 60
                in_game_timer = {'in_game_period': 1,
                                 'in_game_timer': time_difference,
                                 'min': min_,
                                 'sec': sec_}
                return in_game_timer

            # Start_2nd_half
            elif event_code_id in [12, 13]:
                # Re-calculate the kick-off time of 2nd half
                self.target_time = current_time
                self.period = 2
                time_difference = int((current_time - self.target_time).total_seconds()) + 2700
                min_ = time_difference // 60
                sec_ = time_difference % 60
                in_game_timer = {'in_game_period': 2,
                                 'in_game_timer': time_difference,
                                 'min': min_,
                                 'sec': sec_}

                return in_game_timer

            # Stop_2nd_half
            elif event_code_id == 3:
                self.period = 22
                time_difference = 5400
                min_ = time_difference // 60
                sec_ = time_difference % 60
                in_game_timer = {'in_game_period': 2,
                                 'in_game_timer': time_difference,
                                 'min': min_,
                                 'sec': sec_}
                return in_game_timer
            else:
                raise Exception("There is error is Timer")

        else:
            # Calculate Time difference and min and sec
            if self.period in [0, 11, 22]:
                in_game_timer = {'in_game_period': self.period,
                                 'in_game_timer': time_difference,
                                 'min': None,
                                 'sec': None}
                return in_game_timer

            elif self.period == 1:
                time_difference = int((current_time - self.target_time).total_seconds())
            elif self.period == 2:
                time_difference = int((current_time - self.target_time).total_seconds()) + 2700

            min_ = time_difference // 60
            sec_ = time_difference % 60
            in_game_timer = {'in_game_period': self.period,
                             'in_game_timer': time_difference,
                             'min': min_,
                             'sec': sec_}

            return in_game_timer


# -------------- DEFINE CLASS FOR API ENGINE -------------- #
class Engine:
    def __init__(self,
                 match_id,
                 event_code_ids,
                 selected_ids,
                 destination_dir,
                 event_position: int = 0):
        # define url
        self.url_oddsfeed = 'http://210.57.28.64:22212/api/OddsFeed'
        self.url_feeddata = 'http://210.57.28.64:22212/api/FeedData'

        # initialize
        self.match_id = match_id
        self.event_position = event_position
        self.event_code_ids = event_code_ids
        self.selected_ids = selected_ids
        self.destination_dir = destination_dir

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
        self.live_timer = Timer()
        self.full_rb_events = []
        self.event_data_ft = None
        self.event_data_ht = None
        self.is_running = True

        # Create the log
        self.create_log(directory_path=self.destination_dir)

        # get feed info
        self.GetFeedInfo()
        print(f"---- Starting to fetch data of match id: {self.match_id}")
        logging.info(f'---- Starting to fetch data of match id: {self.match_id}')

    # ------------------ FUNCTION TO GET FEED IFO----------------------
    def GetFeedInfo(self):
        url = self.url_feeddata + '/GetFeedMappingInfo?matchId=' + str(self.match_id)
        response = requests.get(url)
        data = response.json()
        self.feed_id = data['feedId']
        self.feed_source = data['feedSource']
        # self.feed_reverse = data['feedReverse']

    # ------------------ CREATE THE LOG FILE ----------------------
    def create_log(self, directory_path='api_folder/'):
        # Get the username of the person who is running the script.
        USERNAME = getpass.getuser()

        # Set a format to the logs.
        LOG_FORMAT = '[%(levelname)s | ' + USERNAME + ' | %(asctime)s] - %(message)s'

        # Name of the file to store the logs.
        log_filename = os.path.join(directory_path,
                                    str(self.match_id),
                                    f'live_{self.match_id}_log.txt')
        directory_path = os.path.split(log_filename)[0]
        self.create_directory(dir_path=directory_path)
        LOG_FILENAME = log_filename

        # set log level
        LOG_LEVEL = logging.INFO

        # == Set up logging ============================================================
        logging.basicConfig(
            level=LOG_LEVEL,
            format=LOG_FORMAT,
            force=True,
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[logging.FileHandler(LOG_FILENAME, "a", "utf-8"),
                      logging.StreamHandler()]
        )
        print(f'>>>> Log file was created in {log_filename}')
        # Log the script execution start
        logging.info(f'>>>> Log file was created in {log_filename}')

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
            pd.concat([period_1_df, period_2_df])
            .sort_values(by=['in_game_period', 'min'])
            .reset_index(drop=True)[['in_game_period', 'in_game_timer', 'min', 'sec']]
        )
        timer = df_time.to_dict(orient='records')

        return timer

    # ------------------ FUNCTION TO STRUCTURE THE ADMIN DATA ----------------------
    def get_AB_timer_metadata(self, isFT=True, is_live: bool = True):
        url = self.url_oddsfeed + f'/GetLiveMatchAbility?isFT={isFT}&matchId={self.match_id}'
        # print(f"Starting to fetch the API:{url}")
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
        # Get starting time
        match_details = js_admin['matchLeague']
        target_time = self.live_timer.convert_target_time(target_time=str(match_details['liveTimer']))

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

        l_timer = {'KickoffTime': kick_off_time,
                   "LiveTimer": math.floor(ig_seconds),
                   'min': math.floor(ig_seconds // 60),
                   'sec': math.floor(ig_seconds % 60),
                   "LivePeriod": match_details["livePeriod"],
                   'isRunning': True if match_details['eventStatus'] == 'running' else False}

        # Create a new dictionary with the desired structure
        final_data = {'Ability': Ability,
                      'Match': Match,
                      'Timer': l_timer}

        return final_data

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
    # Check directory
    def create_directory(self, dir_path):
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

    def save_json(self,
                  is_live_match: bool):
        # Check directory input
        file_directory = os.path.join(self.destination_dir, str(self.match_id))
        self.create_directory(dir_path=file_directory)
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
        print(f'---- Dictionary saved to:\n{self.full_path[0]}\n{self.full_path[1]}\n----')
        logging.info(f'---- \nDictionary saved to:\n{self.full_path[0]}\n{self.full_path[1]}')
        logging.shutdown()

    # ------------------ FUNCTION TO CALL API FOR PAST MATCH ----------------------
    def get_logs_for_past_match(self, isFT: bool):
        # --- CREATE ADMIN DATA ---
        admin_data = self.get_AB_timer_metadata(isFT=isFT, is_live=False)

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
            # filter_2 =

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
        rows = test[test['eventCodeId'] == 3].shape[0]
        if rows > 1:
            last_ig_index = test[test['eventCodeId'] == 3].index[1]
            full_match = test.iloc[:last_ig_index, :].dropna().reset_index(drop=True)
        else:
            full_match = test.dropna().reset_index(drop=True)

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
    def get_logs_for_current_match(self):

        # --- DEFINE FUNCTION TO HANDLE EVENT---
        def get_keys(dictionary, keys: list):
            return {key: dictionary[key] for key in keys}

        def processing_event(ev):
            # Change period state:
            if ev['sportsTickerStateId'] == 2:
                ev['in_game_period'] = 1
            elif ev['sportsTickerStateId'] == 8:
                ev['in_game_period'] = 2
            else:
                if ev['eventCode_Desc'] == 'Stop 1st half':
                    ev['in_game_period'] = 1
                elif ev['eventCode_Desc'] == 'Stop 2nd half':
                    ev['in_game_period'] = 2
                else:
                    ev['in_game_period'] = 0
            # remove sportsTickerStateId:
            ev.pop('sportsTickerStateId', None)
            # calculate in-game timer
            ev['in_game_timer'] = ev['min'] * 60 + ev['sec']
            return ev

        # ------------- INITIALIZATION -----------------------
        # CREATE ADMIN DATA
        admin_data = self.get_AB_timer_metadata(is_live=True)

        # Create the event counter and get last event
        if len(self.full_api_ls) > 0:
            event_counter = self.full_api_ls[-1]['Event']
            last_event_counter = copy.deepcopy(self.full_api_ls[-1]['Event'])
        else:
            event_counter = {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}
            last_event_counter = {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}

        # Get Running ball event
        # current_position = self.event_position  # Start from 0 and gradually increase until the end
        js_rb = self.get_rb_events()

        # format js_rb
        selected_keys = ['eventNumber', 'eventCodeId',  # 'homeScore', 'awayScore', 'timestamp',
                         'sportsTickerStateId', 'min', 'sec', 'eventCode_Desc']

        js_rb = [get_keys(dictionary=e_dict, keys=selected_keys) for e_dict in js_rb]
        # print("check js_rb")
        # display = [get_keys(dictionary=e_dict, keys=['eventNumber', 'eventCodeId','min', 'sec', 'eventCode_Desc']) for e_dict in js_rb]
        # pprint(display)

        # -----------CALCULATE IN-GAME TIMER ---------------
        # game still not starts yet
        if len(js_rb) == 0 and len(self.full_rb_events) == 0:
            rb_data = {'ingame_Timer': {'in_game_period': 0, 'in_game_timer': 0, 'min': 0, 'sec': 0},
                       'Event': event_counter,
                       'LastEvent': last_event_counter}

        else:  # len(self.full_rb_events) >= 0 a>0 and b=0 , a>0 and b>0, a=0 and b>0
            if len(js_rb) == 0:
                in_game_timer = self.live_timer.create_time_counter(event_code_id=None)

                # create final output
                rb_data = {'ingame_Timer': in_game_timer,
                           'Event': event_counter,
                           'LastEvent': last_event_counter}
            else:
                code_id_ls = [int(f['eventCodeId']) for f in js_rb]
                selected_ids = [10, 11, 1, 12, 13, 3]
                update_ls = list(set(code_id_ls) & set(selected_ids))

                # If Trigger some code id => Update Target time
                if len(update_ls) > 0:
                    in_game_timer = self.live_timer.create_time_counter(event_code_id=update_ls[0])
                    print(f"---Target time is updated to {self.live_timer.target_time}\t Update list: {update_ls}\t Ingame timer: {in_game_timer}")
                else:
                    in_game_timer = self.live_timer.create_time_counter(event_code_id=None)
                    # print(f"---Ingame timer: {in_game_timer}")

                # ----------- UPDATE RUNNING BALL EVENT COUNTER ---------------
                # define some code should be eliminated
                focus = [1024, 2048, 1052, 2076, 1051, 2075]
                remove = [1075, 2099, 1074, 2098, 1076, 2100]

                # loop the js_rb to get events
                for i, event in enumerate(js_rb):
                    # Preprocessing event
                    event = processing_event(ev=event)
                    # Update event position
                    self.event_position = event['eventNumber']

                    # Preprocess rb event
                    event_code_id = event['eventCodeId']

                    # Case 1: there is the rb event, but it is not in-game event (Period 1) => hold the counter
                    if in_game_timer['in_game_period'] in [0, 11, 22]:
                        # Update counter
                        rb_data = {'ingame_Timer': in_game_timer,
                                   'Event': event_counter,
                                   'LastEvent': last_event_counter}

                        # Append event
                        self.full_rb_events.append(event)

                    # Case 2: there are events in period 1 and 2
                    else:
                        # --- Ignore the duplicated events ---
                        # Get previous event:
                        previous_event = self.full_rb_events[-1] if i == 0 else js_rb[i - 1]

                        #  Check if the current event and previous event have the same purpose based on 'eventCodeId'
                        filter_1 = (event_code_id in remove) and ((previous_event['eventCodeId'] in focus)
                                                                  or (previous_event['eventCodeId'] in remove))

                        # Remove the consecutive event
                        if (filter_1 is False) and (event_code_id in self.rb_code_ls):
                            code_event = self.selected_ids[str(event_code_id)]['code']
                            event_counter[code_event] += 1
                            event_counter_copy = copy.deepcopy(event_counter)

                            # Update counter
                            rb_data = {'ingame_Timer': in_game_timer,
                                       'Event': event_counter_copy,
                                       'LastEvent': last_event_counter}

                        else:
                            rb_data = {'ingame_Timer': in_game_timer,
                                       'Event': event_counter,
                                       'LastEvent': last_event_counter}

                        # Append event
                        self.full_rb_events.append(event)

        # ------------------- Update data -----------------------
        # Merge rb_data with admin_data
        admin_data.update(rb_data)

        # Stop calling API when the 2nd half finishes
        if admin_data['ingame_Timer']['in_game_period'] == 2 and admin_data['Event']['Stop_2nd_half'] > 0:
            print('>>>> Finish the game')
            logging.info('>>>> Finish the game')
            self.is_running = False

        # ---- EXAMINE WHICH THE EVENT CODE IS COUNTED -------
        keys = list(admin_data['Event'].keys())
        diff_event_counter = np.array(list(admin_data['Event'].values())) - np.array(list(admin_data['LastEvent'].values()))
        timer = {key: admin_data['ingame_Timer'][key] for key in ['in_game_period', 'min', 'sec']}
        event_change = {keys[i]: v for i, v in enumerate(diff_event_counter) if v > 0}
        final = timer.copy()
        final.update(event_change)

        if len(event_change) > 0:
            print(f'--- There is update event:\n{final}')
            logging.info(f'--- There is update event:\n{final}')

        # ---- IF THE PERIOD NOT IN [1,2] => RETURN NONE -------
        if admin_data['ingame_Timer']['in_game_period'] in [0, 11, 22]:
            return admin_data
        elif admin_data['ingame_Timer']['in_game_period'] in [1, 2]:
            self.full_api_ls.append(admin_data)
            ig_ = admin_data['ingame_Timer']
            print(f" --- Fetching data at period: {ig_['in_game_period']}\t{ig_['min']} mins {ig_['sec']} secs\n\n")
            return admin_data


if __name__ == '__main__':
    match_id_ = 77506141  # 78534882  # 78378471 #77422531 #78329100 #78327701 #78088596 #77854937 #77926259 #77623787 #77592032
    position = 0
    event_code_ids = []
    dest_path = r'C:\Users\user2\PycharmProjects\Livescore_model\TEST_API\api_folder'

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
    # while is_running:
    for i in range(5):

        log_api = match.get_logs_for_current_match()
        period = log_api['ingame_Timer']['in_game_period']
        # js_adm, final_output = match.get_AB_timer_metadata(isFT=True,is_live=True)
        # time.sleep(0.2)

        if period in [0, 11, 22]:
            print(f'--- It remains {final_output["Timer"]["min"]} mins {final_output["Timer"]["sec"]} secs before staring games\n\n')

        elif period in [1, 2]:
            print(log_api)

        is_running = match.is_running

    # ------------- SAVE LOG FILE FOR LIVE MATCH -------------
    # pprint(match.full_rb_events)
    match.save_json(is_live_match=True)
