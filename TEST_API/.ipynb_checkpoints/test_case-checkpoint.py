from live_data_format import Engine
import time
import json
import copy


#TestCase

match_id = 77592032
event_position = 0
event_code_ids = []

json_file_path = 'rb_code.json'
# Open the file and load the JSON data
with open(json_file_path, 'r') as json_file:
    rb_code = json.load(json_file)

match = Engine(match_id,event_position,event_code_ids,rb_code)


logs=[]
for i in range(5):
    
    
    #get FT event
    match.UpdateLogs(True)
    logs.append(copy.deepcopy(match.event_data_ft))
    #get HT event
    #match.UpdateLogs(False)
    #logs.append(copy.deepcopy(match.event_data_ht))
    
    #simulate request every 5 seconds
    time.sleep(5)
    pass


print(logs)

pass    