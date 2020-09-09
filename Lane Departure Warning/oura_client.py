import json
import urllib.request
import datetime
import certifi
import ssl
import os
import time

# URL access variables
access_token = 'WBR5SYQD7US3GG6BYNAAKKGC3MGPAS6G'
url_userinfo = 'https://api.ouraring.com/v1/userinfo?access_token='
url_sleep = 'https://api.ouraring.com/v1/sleep?access_token='
url_activity = 'https://api.ouraring.com/v1/activity?access_token='
url_readiness = 'https://api.ouraring.com/v1/readiness?access_token='
start_tag = '&start='
end_tag = '&end='

# date/time variables
today = datetime.date.today()
yesterday = today - datetime.timedelta(days = 1)
today = str(today)
yesterday = str(yesterday)

# human states
attentive = 0
moderate = 1
unattentive = 2
dict_states = {attentive: "attentive", moderate: "moderate", unattentive: "unattentive"}

# functions to receive Oura ring data
def get_userinfo(start=today, end=today):
    url = url_userinfo + access_token + start_tag + start + end_tag + end
    data = urllib.request.urlopen(url, context=ssl.create_default_context(cafile=certifi.where())).read().decode()
    obj = json.loads(data)
    return obj
def get_sleep(start=yesterday, end=today):
    url = url_sleep + access_token + start_tag + start + end_tag + end
    data = urllib.request.urlopen(url, context=ssl.create_default_context(cafile=certifi.where())).read().decode()
    obj = json.loads(data)
    return obj
def get_activity(start=today, end=today):
    url = url_activity + access_token + start_tag + start + end_tag + end
    data = urllib.request.urlopen(url, context=ssl.create_default_context(cafile=certifi.where())).read().decode()
    obj = json.loads(data)
    return obj
def get_readiness(start=yesterday, end=today):
    url = url_readiness + access_token + start_tag + start + end_tag + end
    data = urllib.request.urlopen(url, context=ssl.create_default_context(cafile=certifi.where())).read().decode()
    obj = json.loads(data)
    return obj
def get_all_data():
    userinfo = get_userinfo()
    sleep = get_sleep()
    activity = get_activity()
    readiness = get_readiness()
    return userinfo, sleep, activity, readiness

# helper functions
def get_current_state():
    userinfo, sleep, activity, readiness = get_all_data()
    sleep_state = calculate_sleep(sleep)
    activity_state = calculate_activity(activity)
    readiness_state = calculate_readiness(readiness)
    current_state = classify_state(userinfo, sleep_state, activity_state, readiness_state)
    return current_state
def print_json():
    userinfo = get_userinfo()
    sleep = get_sleep()
    activity = get_activity()
    readiness = get_readiness()
    print("User info:")
    print(userinfo)
    print("\nSleep:")
    print(sleep)
    print("\nActivity:")
    print(activity)
    print("\nReadiness:")
    print(readiness)
def save_json():
    if(not(os.path.exists('Oura Data'))):
        os.mkdir('Oura Data')
    os.chdir('Oura Data')
    userinfo_outfile = open('UserInfo.json', 'w')
    sleep_outfile = open('Sleep.json', 'w')
    activity_outfile = open('Activity.json', 'w')
    readiness_outfile = open('Readiness.json', 'w')
    userinfo, sleep, activity, readiness = get_all_data()
    json.dump(userinfo, userinfo_outfile)
    json.dump(sleep, sleep_outfile)
    json.dump(activity, activity_outfile)
    json.dump(readiness, readiness_outfile)
    os.chdir('..')

# human state calculation/classification functions
def calculate_sleep(file):
    if(len(file['sleep']) == 0):
        return None
    path = file['sleep'][0]
    # metrics
    score = path['score']
    if(score == 0):
        return None
    restless = path['restless']/100
    hr_average = path['hr_average']
    duration = path['duration']/3600
    efficiency = path['efficiency']/100
    # calculations
    sleep_state = (efficiency - restless) * score
    if(efficiency == 0 or restless == 0):
        sleep_state = score
    if(hr_average >= 100):
        sleep_state -= sleep_state * 0.25
    if(duration < 7 and duration != 0):
        sleep_state -= sleep_state * 0.10
    return sleep_state
def calculate_activity(file):
    if(len(file['activity']) == 0):
        return None
    path = file['activity'][0]
    # metrics
    score = path['score']
    if(score == 0):
        return None
    return score
def calculate_readiness(file):
    if(len(file['readiness']) == 0):
        return None
    path = file['readiness'][0]
    # metrics
    score = path['score']
    if(score == 0):
        return None
    score_recovery_index = path['score_recovery_index']
    score_resting_hr = path['score_resting_hr']
    score_temperature = path['score_temperature']
    other_metrics = [score_recovery_index, score_resting_hr, score_temperature]
    size = 3
    for metric in other_metrics:
        if(metric == 0):
            size -= 1
    # calculations
    if(size != 0):
        avg_other_scores = (score_recovery_index + score_resting_hr + score_temperature)/size
    else:
        return score
    readiness_state = (score + 0.5 * avg_other_scores)/1.5
    return readiness_state
def classify_state(userinfo, sleep_state, activity_state, readiness_state):
    age = userinfo['age']
    if(readiness_state is None):
        return moderate # default value if no data is provided
    if(sleep_state is None):
        sleep_state = readiness_state
    if(activity_state is None):
        activity_state = readiness_state
    average_state_score = (sleep_state + (activity_state * 0.25) + readiness_state)/2.25
    if(age > 65):
        average_state_score -= average_state_score * 0.10
    # classifying into three human states
    if(average_state_score >= 75):
        return attentive
    elif(average_state_score > 50 and average_state_score < 75):
        return moderate
    else:
        return unattentive
        