import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pytz
import tzlocal
import os
import pathlib

class Engine:
    def __init__(self, match_id, event_code_ids, selected_ids) -> None:
        # define url
        self.url_oddsfeed = 'http://210.57.28.64:22212/api/OddsFeed'
        self.url_feeddata = 'http://210.57.28.64:22212/api/FeedData'

        # initialize
        self.match_id = match_id
        self.event_position = 0
        self.event_code_ids = event_code_ids
        self.selected_ids = selected_ids
        self.event_data_ft = None
        self.event_data_ht = None
        self.feed_id = None
        self.feed_source = None
        self.match_event_info = []
        self.match_event_counter = []
        self.full_api_ls = []
        self.remove_id = [2100, 1076, 228, 1073, 2097, 207]
        self.rb_code_ls = [int(i) for i in self.selected_ids.keys() if int(i) not in self.remove_id]

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

    # ------------------ FUNCTION TO ADJUST THE  OFFSET OF TIMEZONE----------------------
    def _get_utc_offset(self, dt):
        # Get the time zone from the datetime object
        current_timezone = dt.astimezone().tzinfo

        # Get the UTC offset as a timedelta
        utc_offset = current_timezone.utcoffset(dt)

        # Extract hours and minutes from the UTC offset timedelta
        offset_hours, _ = divmod(utc_offset.seconds // 60, 60)

        # Return the UTC offset as integers
        return offset_hours + 4

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
        df_time = (pd.concat([period_1_df, period_2_df]).sort_values(by=['in_game_period', 'min']).reset_index(drop=True)[['in_game_period', 'in_game_timer', 'min', 'sec']])
        timer = df_time.to_dict(orient='records')

        return timer

    # ------------------ FUNCTION TO STRUCTURE THE ADMIN DATA ----------------------
    def Get_AB_timer_metadata(self, isFT=True):
        url = self.url_oddsfeed + f'/GetLiveMatchAbility?isFT={isFT}&matchId={self.match_id}'
        response = requests.get(url)
        js_admin = response.json()

        # -- get initial abilities --
        Ability = {"Home": js_admin["ability"]["home"],
                   "Away": js_admin["ability"]["away"]}

        # -- get metadata of match --
        Match = {"MatchTime": 90,
                 "LeagueId": js_admin["matchLeague"]["leagueId"],
                 "MatchID": js_admin["matchLeague"]["matchId"],
                 "HomeTeamId": js_admin["matchLeague"]["homeId"],
                 "AwayTeamId": js_admin["matchLeague"]["awayId"]}

        # -- TIMER --
        # Get the current time
        current_time = datetime.now()

        # Get the utc offset
        utc_offset = self._get_utc_offset(dt=current_time)

        # Get starting time
        match_details = js_admin['matchLeague']
        target_time = match_details['kickOffTime']
        date_parts = target_time.split('.')
        date_format = "%Y-%m-%dT%H:%M:%S"
        target_time = datetime.strptime(date_parts[0], date_format) + timedelta(hours=utc_offset)

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
        local_tz = tzlocal.get_localzone().key

        # add timezone into datetime objet
        obj_tz = pytz.timezone(local_tz).localize(target_time)
        kick_off_time = obj_tz.strftime("%Y-%m-%dT%H:%M:%S %z")

        Timer = {'KickoffTime': kick_off_time,
                 "LiveTimer": int(ig_seconds),
                 # 'mins': int(ig_seconds//60),
                 # 'secs': int(ig_seconds%60),
                 "LivePeriod": js_admin["matchLeague"]["livePeriod"],
                 'isRunning': True if js_admin["matchLeague"]['eventStatus'] == 'running' else False}

        # Create a new dictionary with the desired structure
        final_data = {'Ability': Ability,
                      'Match': Match,
                      'Timer': Timer}

        return js_admin, final_data

    # ------------------ FUNCTION TO GET RUNNING BALL EVENT ----------------------
    def _get_rb_events(self):
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
    def save_json(self, file_directory='api_folder/'):

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
        json_file_name = f'full_api_{self.match_id}.json'
        full_path = os.path.join(file_directory, json_file_name)

        # Save the dictionary to a JSON file
        with open(full_path, 'w') as json_file:
            json.dump(self.full_api_ls, json_file, indent=4)
        print(f'Dictionary saved to {full_path}')

    # ------------------ FUNCTION TO CALL API FOR PAST MATCH ----------------------
    def get_logs_for_past_match(self, isFT: bool):
        # --- CREATE ADMIN DATA ---
        js_admin, admin_data = self.Get_AB_timer_metadata(isFT=True)

        # --- Get Running ball event ---
        js_rb = self._get_rb_events()

        # --- Create the event counter ---
        if isFT:
            if self.event_data_ft is not None:
                event_counter = self.event_data_ft['Event']
            else:
                event_counter = {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}
        else:
            if self.event_data_ht is not None:
                event_counter = self.event_data_ht['Event']
            else:
                event_counter = {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}

        # define some code should be eliminated
        atk_h = [1024, 1075]
        atk_a = [2048, 2099]

        safe_h = [1051, 1074]
        safe_a = [2075, 2098]

        dan_h = [1052, 1076]
        dan_a = [2076, 2100]

        for i, event in enumerate(js_rb):
            event_dict = {key: event[key] for key in ['eventNumber', 'eventCodeId', 'homeScore', 'awayScore',
                                                      'sportsTickerStateId', 'min', 'sec', 'eventCode_Desc']}
            event_code_id = event_dict['eventCodeId']

            # Remove consecutive event based on 'eventCodeId'
            filter_1 = (event_dict['eventCodeId'] in atk_h) and (js_rb[i - 1]['eventCodeId'] in atk_h)
            filter_2 = (event_dict['eventCodeId'] in atk_a) and (js_rb[i - 1]['eventCodeId'] in atk_a)
            filter_3 = (event_dict['eventCodeId'] in safe_h) and (js_rb[i - 1]['eventCodeId'] in safe_h)
            filter_4 = (event_dict['eventCodeId'] in safe_a) and (js_rb[i - 1]['eventCodeId'] in safe_a)
            filter_5 = (event_dict['eventCodeId'] in dan_h) and (js_rb[i - 1]['eventCodeId'] in dan_h)
            filter_6 = (event_dict['eventCodeId'] in dan_a) and (js_rb[i - 1]['eventCodeId'] in dan_a)

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
            if any([filter_1, filter_2, filter_3, filter_4, filter_5, filter_6]):
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
                # elif event_dict['eventCodeId'] in dan_h:
                #     event_dict['eventCodeId'] = dan_h[0]
                # elif event_dict['eventCodeId'] in dan_a:
                #     event_dict['eventCodeId'] = dan_a[0]

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
        full_match = test.iloc[:last_ig_index, :]

        # Create the final output:
        for i, igp, igt, m, s, k in full_match[['in_game_period', 'in_game_timer', 'min', 'sec', 'key']].itertuples(index=True):
            k_ = int(k)
            if i == 0:
                final_output = {'ingame_Timer': {'in_game_period': igp, 'in_game_timer': igt, 'min': m, 'sec': s},
                                'Event': self.match_event_counter[k_],
                                'LastEvent': self.match_event_counter[k_]}
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
    def get_logs_for_current_match(self,isFT:bool=True):
        # --- CREATE ADMIN DATA ---
        js_admin, admin_data = self.Get_AB_timer_metadata(isFT=isFT)

        # --- Get Running ball event ---
        js_rb = self._get_rb_events()

        # --- Create the event counter ---
        if isFT:
            if self.event_data_ft is not None:
                event_counter = self.event_data_ft['Event']
            else:
                event_counter = {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}
        else:
            if self.event_data_ht is not None:
                event_counter = self.event_data_ht['Event']
            else:
                event_counter = {v['code']: 0 for k, v in self.selected_ids.items() if k not in self.remove_id}

        # Get last event
        home_score = event_counter['Score1']
        away_score = event_counter['Score2']
        last_event_data = event_counter.copy()

        # define some code should be eliminated
        atk_h = [1024, 1075]
        atk_a = [2048, 2099]

        safe_h = [1051, 1074]
        safe_a = [2075, 2098]

        dan_h = [1052, 1076]
        dan_a = [2076, 2100]

        for i, event in enumerate(js_rb):
            event_dict = {key: event[key] for key in ['eventNumber', 'eventCodeId', 'homeScore', 'awayScore',
                                                      'sportsTickerStateId', 'min', 'sec', 'eventCode_Desc']}
            event_code_id = event_dict['eventCodeId']

            # Remove consecutive event based on 'eventCodeId'
            filter_1 = (event_dict['eventCodeId'] in atk_h) and (js_rb[i - 1]['eventCodeId'] in atk_h)
            filter_2 = (event_dict['eventCodeId'] in atk_a) and (js_rb[i - 1]['eventCodeId'] in atk_a)
            filter_3 = (event_dict['eventCodeId'] in safe_h) and (js_rb[i - 1]['eventCodeId'] in safe_h)
            filter_4 = (event_dict['eventCodeId'] in safe_a) and (js_rb[i - 1]['eventCodeId'] in safe_a)
            filter_5 = (event_dict['eventCodeId'] in dan_h) and (js_rb[i - 1]['eventCodeId'] in dan_h)
            filter_6 = (event_dict['eventCodeId'] in dan_a) and (js_rb[i - 1]['eventCodeId'] in dan_a)

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
            if any([filter_1, filter_2, filter_3, filter_4, filter_5, filter_6]):
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
                # elif event_dict['eventCodeId'] in dan_h:
                #     event_dict['eventCodeId'] = dan_h[0]
                # elif event_dict['eventCodeId'] in dan_a:
                #     event_dict['eventCodeId'] = dan_a[0]

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
        full_match = test.iloc[:last_ig_index, :]

        # Create the final output:
        for i, igp, igt, m, s, k in full_match[['in_game_period', 'in_game_timer', 'min', 'sec', 'key']].itertuples(index=True):
            k_ = int(k)
            if i == 0:
                final_output = {'ingame_Timer': {'in_game_period': igp, 'in_game_timer': igt, 'min': m, 'sec': s},
                                'Event': self.match_event_counter[k_],
                                'LastEvent': self.match_event_counter[k_]}
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


if __name__ == '__main__':
    match_id = 77926259  # 77623787 #77592032
    event_code_ids = []

    json_file_path = 'rb_code_upd.json'
    # Open the file and load the JSON data
    with open(json_file_path, 'r') as json_file:
        rb_code = json.load(json_file)

    match = Engine(match_id=match_id,
                   event_code_ids=event_code_ids,
                   selected_ids=rb_code)

    log_api = match.get_logs_for_past_match(isFT=True)

    match.save_json(file_directory='api_folder')