from datetime import datetime, timedelta
import pytz
import tzlocal


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

    def convert_target_time(self, target_time):
        # Get the utc offset
        utc_offset = self._get_utc_offset()

        # Convert datetime
        date_parts = target_time.split('.')
        date_format = "%Y-%m-%dT%H:%M:%S"
        self.target_time = datetime.strptime(date_parts[0], date_format) + timedelta(hours=utc_offset)
        return self.target_time

    def create_time_counter(self, event_code_id=None):
        current_time = datetime.now().replace(microsecond=0)
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
