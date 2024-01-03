import requests
import numpy as np
import json
from datetime import datetime, timedelta


class Engine:
    global url_oddsfeed
    global url_feeddata

    url_oddsfeed = 'http://210.57.28.64:22212/api/OddsFeed'
    url_feeddata = 'http://210.57.28.64:22212/api/FeedData'

    def __init__(self, match_id, event_position, event_code_ids, selected_ids) -> None:

        def GetFeedInfo(self):
            self.match_id

            url = url_feeddata + '/GetFeedMappingInfo?matchId=' + str(self.match_id)

            response = requests.get(url)
            data = response.json()

            self.feed_id = data['feedId']
            self.feed_source = data['feedSource']
            self.feed_reverse = data['feedReverse']
            self.event_data_ft = None
            self.event_data_ht = None

        # initialize
        self.match_id = match_id
        self.event_position = event_position
        self.event_code_ids = event_code_ids
        self.selected_ids = selected_ids

        # get feed info
        GetFeedInfo(self)

    def UpdateLogs(self, isFT: bool):

        def get_utc_offset(dt):
            # Get the time zone from the datetime object
            current_timezone = dt.astimezone().tzinfo

            # Get the UTC offset as a timedelta
            utc_offset = current_timezone.utcoffset(dt)

            # Extract hours and minutes from the UTC offset timedelta
            offset_hours, _ = divmod(utc_offset.seconds // 60, 60)

            # Return the UTC offset as integers
            return offset_hours + 4

        last_event_data = None

        if isFT:
            if not self.event_data_ft is None:
                event_data = self.event_data_ft['Event']
                last_event_data = event_data.copy()
            else:
                event_data = event_data = {value['code']: 0 for value in self.selected_ids.values()}
        else:
            if not self.event_data_ht is None:
                event_data = self.event_data_ht['Event']
                last_event_data = event_data.copy()
            else:
                event_data = event_data = {value['code']: 0 for value in self.selected_ids.values()}

        max_event_num = self.event_position

        url = url_oddsfeed + f'/GetLiveMatchAbility?isFT={isFT}&matchId={self.match_id}'

        response = requests.get(url)

        # convert into json
        js_admin = response.json()

        # Get Feed Events
        body = {'sportTickerId': self.feed_id,
                'feedSource': self.feed_source,
                'lastEventNumber': self.event_position,
                'eventCodeIdList': self.event_code_ids
                }
        header = {'content-type': 'application/json', 'accept': 'text/plain'}

        s_url = url_feeddata + '/GetFeedEvents'
        response = requests.post(url=s_url, json=body, headers=header)

        # convert into json
        js_rb = response.json()

        # get data start time convert str date to Date
        self.match_details = js_admin['matchLeague']

        # Get the current time
        current_time = datetime.now()

        # Get the utc offset
        utc_offset = get_utc_offset(current_time)

        # Get starting time
        target_time = self.match_details['liveTimer']
        date_parts = target_time.split('.')
        date_format = "%Y-%m-%dT%H:%M:%S"
        target_time = datetime.strptime(date_parts[0], date_format) + timedelta(hours=utc_offset)
        milliseconds = int(date_parts[1])  # |* 10  # Convert to microseconds
        target_time = target_time.replace(microsecond=milliseconds)

        # Calculate the time difference
        time_difference = current_time - target_time

        # calculate ingame time
        ig_seconds = time_difference.total_seconds()

        # check if game is 2nd half, add 45mins
        if self.match_details['livePeriod'] == 2:
            ig_seconds += 2700

        # check if HT then keep ig_seconds constant
        if self.match_details['isHT']:
            ig_seconds = 2700

        # Create a new dictionary with the desired structure
        admin_data = {
            "Ability": {
                "Home": js_admin["ability"]["home"],
                "Away": js_admin["ability"]["away"]
            },
            "Match": {
                "MatchTime": 90,
                "LeagueId": js_admin["matchLeague"]["leagueId"],
                "MatchID": js_admin["matchLeague"]["matchId"],
                "HomeTeamId": js_admin["matchLeague"]["homeId"],
                "AwayTeamId": js_admin["matchLeague"]["awayId"]
            },
            "Timer": {
                "LiveTimer": ig_seconds,
                "LivePeriod": js_admin["matchLeague"]["livePeriod"]
            }
        }

        # remove consecutive event based on 'eventCodeId'
        filtered_data = []
        for i in range(1, len(js_rb)):
            if js_rb[i]['eventCodeId'] != js_rb[i - 1]['eventCodeId']:
                filtered_data.append(js_rb[i])
                event_num = js_rb[i]['eventNumber']

                if event_num is not None:
                    if max_event_num is None or event_num > max_event_num:
                        max_event_num = event_num

        if len(filtered_data) > 0:

            for item in filtered_data:
                event_code_id = str(item.get("eventCodeId"))
                if event_code_id in self.selected_ids:
                    event_data[self.selected_ids[event_code_id]['code']] += 1

                rb_time = item['min'] * 60 + item['sec']
                home_score = item['homeScore']
                away_score = item['awayScore']

                # get last event_number
                event_position = item['eventNumber']

            # modify event_data
            event_data['GOAL1'] = home_score
            event_data['GOAL2'] = away_score

            # add rb_time into admin_data
            admin_data['Timer']['ProviderTimer'] = rb_time

            # create a dictionary with rb
            rb_data = {
                'Event': event_data,
                'LastEvent': last_event_data
            }

            # Merge rb_data with admin_data
            admin_data.update(rb_data)

            if isFT:
                self.event_data_ft = admin_data
            else:
                self.event_data_ht = admin_data

            self.event_position = event_position

        pass
