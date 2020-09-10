import glob
import os
import sys

import socket
import pickle
import math
import time
import threading
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tqdm import trange
import argparse
import json

# probability for exploration
epsilon = 0.1

# step size
alpha = 0.5

# gamma for Q-Learning
gamma = 0.99

# rate at which state transitions are measured
sampling_rate = 0.1
vector_size = int(2/sampling_rate)

# human states
attentive = 0
moderate = 1
unattentive = 2
human_state = None
dict_human_states = {"attentive": attentive, "moderate": moderate, "unattentive": unattentive}

# number of states per dimension
num_distance_states = 12
num_speed_states = 3
num_human_states = 3

# q-value lookup table, initialized to zeros
q_values = np.zeros((num_distance_states, num_speed_states, num_human_states, 2))

# iterations for episode
iterations = 100

# actions
no_warning = 0
warning = 1
actions = [no_warning, warning]
dict_actions = {no_warning: "no warning", warning: "warning"}

# files
input_file = None
output_file = None

# connection variables
sock = None
conn = None
d = None
conn_reset = False

# class definitions
class LaneDepartureData:
    location_x = 0
    location_y = 0
    right = 0
    left = 0
    right_x = 0
    right_y = 0
    right_lane_width = 0
    left_x = 0
    left_y = 0
    left_lane_width = 0
    acc_x = 0
    acc_y = 0
    acc_z = 0
    speed = 0
    speed_limit = 0
    lane_id = 0
class State:
    def __init__(self):
        self.metrics = receive_metrics()
        self.value = enumerate_state(self.metrics)
# Q-learning functions
def receive_metrics():
    while True:
        if(d is not None):
            dr = right_lane_distance(d.location_x, d.location_y, d.right_x, d.right_y, d.right_lane_width)
            dl = left_lane_distance(d.location_x, d.location_y, d.left_x, d.left_y, d.left_lane_width)
            if(dr is not None and dl is not None and d.speed_limit is not None and d.speed is not None and d.lane_id is not None):
                dr *= -1
                dl *= -1
                dr = float('%.2f' % dr)
                dl = float('%.2f' % dl)
                speed = d.speed * 2.237 # m/s to mph
                return {"dl": dl, "dr": dr, "speed": speed, "speed_limit": d.speed_limit, "lane_id": d.lane_id}
def initialize_q_table():
    for i in range(0, 3):
        q_values[i, :, :, 0] = 1
        q_values[i, :, :, 1] = 0
    for i in range(5, 8):
        q_values[i, :, :, 0] = 0
        q_values[i, :, :, 1] = 0
    for i in range(8, 12):
        q_values[i, :, :, 0] = 0
        q_values[i, :, :, 1] = 1
def enumerate_state(metrics):
    # initialize state vector
    state = [0, 0, 0]
    # get values from dictionary
    dl = metrics.get("dl")
    dr = metrics.get("dr")
    speed = metrics.get("speed")
    speed_limit = metrics.get("speed_limit")
    # distance
    if(dl == 1.75 and dr == 1.75):
        state[0] = 0
    elif((dl >= 1.6 and dl < 1.75) or (dr >= 1.6 and dr < 1.75)):
        state[0] = 1
    elif((dl >= 1.45 and dl < 1.6) or (dr >= 1.45 and dr < 1.6)):
        state[0] = 2
    elif((dl >= 1.3 and dl < 1.45) or (dr >= 1.3 and dr < 1.45)):
        state[0] = 3
    elif((dl >= 1.15 and dl < 1.3) or (dr >= 1.15 and dr < 1.3)):
        state[0] = 4
    elif((dl >= 1.0 and dl < 1.15) or (dr >= 1.0 and dr < 1.15)):
        state[0] = 5
    elif((dl >= 0.85 and dl < 1.0) or (dr >= 0.85 and dr < 1.0)):
        state[0] = 6
    elif((dl >= 0.7 and dl < 0.85) or (dr >= 0.7 and dr < 0.85)):
        state[0] = 7
    elif((dl >= 0.55 and dl < 0.7) or (dr >= 0.55 and dr < 0.7)):
        state[0] = 8
    elif((dl >= 0.4 and dl < 0.55) or (dr >= 0.4 and dr < 0.55)):
        state[0] = 9
    elif((dl >= 0.25 and dl < 0.4) or (dr >= 0.25 and dr < 0.4)):
        state[0] = 10
    elif(dl < 0.25 or dr < 0.25):
        state[0] = 11
    # speed
    if(speed <= speed_limit * 0.9):
        state[1] = 0
    elif(speed > 0.9 * speed_limit and speed <= 1.1 * speed_limit):
        state[1] = 1
    elif(speed > 1.1 * speed_limit):
        state[1] = 2
    # human
    state[2] = dict_human_states.get(receive_human_state())
    return state
def define_rewards(state, action, next_state):
    reward = 0
    if(state.value[0] > next_state.value[0]):
        reward += 10 * (state.value[0] - next_state.value[0])
    elif(state.value[0] < next_state.value[0]):
        reward += -10 * (next_state.value[0] - state.value[0])
    if(state.value[1] > next_state.value[1]):
        reward += 15 * (state.value[1] - next_state.value[1])
    elif(state.value[1] < next_state.value[1]):
        reward += -15 * (next_state.value[1] - state.value[1])
    lane_id = state.metrics.get("lane_id")
    next_lane_id = next_state.metrics.get("lane_id")
    if(lane_id != next_lane_id): # if lane invasion occurs
        reward -= 50
        return reward
    if(is_intermediate(state.value) and is_intermediate(next_state.value) and action == warning): # if warning "ignored"
        reward -= 20
    if(is_unsafe(state.value) and is_safe(next_state.value)): # if corrective action taken after warning from unsafe to safe state (warning implied)
        reward += 50
    if(is_unsafe(state.value) and is_intermediate(next_state.value)): # if corrective action taken after warning from unsafe to intermediate state (warning implied)
        reward += 30
    if(is_intermediate(state.value) and is_safe(next_state.value) and action == warning): # if corrective action taken after warning from intermediate to safe state
        reward += 20
    if(is_intermediate(state.value) and is_safe(next_state.value) and action == no_warning): # if corrective action taken after no warning from intermediate to safe state
        reward -= 10
    if(is_intermediate(state.value) and is_unsafe(next_state.value) and action == no_warning): # if no warning issued, but next state was unsafe
        reward -= 30
        if(state.value[2] == unattentive):
            reward -= 10
    if(is_intermediate(state.value) and is_unsafe(next_state.value) and action == warning): # if warning issued, but next state was unsafe
        reward += 20
        if(state.value[2] == unattentive):
            reward += 20
    if(state.value[2] == unattentive and action == warning): # giving warning to unattentive driver
        reward += 5
    if(state.value[2] == attentive and action == warning): # giving warning to attentive driver
        reward -= 5
    if(state.value[2] == attentive and action == no_warning): # not giving warning to attentive driver
        reward += 5
    return reward
def is_safe(state_value):
    if(state_value[0] < 3 and state_value[1] <= 1 and state_value[2] <= 1):
        return True
    else:
        return False
def is_intermediate(state_value):
    if(not is_safe(state_value) and not is_unsafe(state_value)):
        return True
    else:
        return False
def is_unsafe(state_value):
    if(state_value[0] >= 8):
        return True
    else:
        return False
def choose_action(state_value):
    if(np.random.binomial(1, epsilon) == 1):
        return np.random.choice(actions)
    else:
        values = q_values[state_value[0], state_value[1], state_value[2], :] # row of values for a given state, any actions
        return np.random.choice([action for action, value in enumerate(values) if value == np.max(values)])
def send_action(action, state):
    if(action == warning):
        string = "WARNING! Approaching lane. State: " + str(state.value)
        conn.send(string.encode())
    else:
        string = "Safe. State: " + str(state.value)
        conn.send(string.encode())
def q_learning(thread, step_size= alpha):
    global q_values
    global rewards
    global vector_size
    iteration_rewards = 0
    init_state = State()
    for i in trange(iterations):
        #if(i/iterations >= 0.5):
            #vector_size = int(2/sampling_rate) # reset vector size halfway through episode
        state_vector = []
        if(is_safe(init_state.value)):
            action = no_warning
        elif(is_unsafe(init_state.value)):
            action = warning
        else:
            action = choose_action(init_state.value)
        if(not thread.is_alive()):
            np.save(output_file, q_values)
            sock.close()
            conn.close()
            print("Disconnected.")
            main()
        send_action(action, init_state)
        for j in range(0, vector_size): # generic response time
            state = State()
            state_vector.append(state)
            time.sleep(sampling_rate)
            next_state = State()
            state_vector.append(next_state)
            if(is_safe(next_state.value) and not is_safe(init_state.value) and j > 1):
                #vector_size = j
                break
        # Q-learning lookup table update
        iteration_rewards = define_rewards(init_state, action, state_vector[-1])
        final_state = state_vector[-1]
        print("Going from state", init_state.value, "to state", final_state.value, "action = ", dict_actions[action], "rewards = ", iteration_rewards)
        delta = step_size * (iteration_rewards + gamma * np.max(q_values[final_state.value[0], final_state.value[1], final_state.value[2], :]) - q_values[init_state.value[0], init_state.value[1], init_state.value[2], action])
        q_values[init_state.value[0], init_state.value[1], init_state.value[2], action] += delta
        print("Δ =", delta)
        np.save(output_file, q_values) # save on each iteration
        init_state = final_state
def right_lane_distance(location_x, location_y, right_x, right_y, right_lane_width):
    if(abs(location_x - right_x) <= 1): # if x are negligibly similar
        if(location_y - right_y < 0):
            lane_marking_y = right_y - right_lane_width/2
            return(location_y - lane_marking_y)
        else:
            lane_marking_y = right_y + right_lane_width/2
            return(lane_marking_y - location_y)
    elif(abs(location_y - right_y) <= 1): # if y are negligibly similar
        if(location_x - right_x < 0):
            lane_marking_x = right_x - right_lane_width/2
            return(location_x - lane_marking_x)
        else:
            lane_marking_x = right_x + right_lane_width/2
            return(lane_marking_x - location_x)
def left_lane_distance(location_x, location_y, left_x, left_y, left_lane_width):
    if(abs(location_x - left_x) <= 1): # if x are negligibly similar
           if(location_y - left_y < 0):
               lane_marking_y = left_y - left_lane_width/2
               return(location_y - lane_marking_y)
           else:
               lane_marking_y = left_y + left_lane_width/2
               return(lane_marking_y - location_y)
    elif(abs(location_y - left_y) <= 1): # if y are negligibly similar
           if(location_x - left_x < 0):
               lane_marking_x = left_x - left_lane_width/2
               return(location_x - lane_marking_x)
           else:
               lane_marking_x = left_x + left_lane_width/2
               return(lane_marking_x - location_x)

# data management functions
def ThreadFunction(conn):
    global d
    global conn_reset
    while True:
        try:
            data = conn.recv(4096)
            d = pickle.loads(data)
        except ConnectionResetError:
            conn_reset = True
            np.save(output_file, q_values) # custom file
            break
        except EOFError:
            conn_reset = True
            np.save(output_file, q_values) # custom file
            break
        except BrokenPipeError:
            conn_reset = True
            np.save(output_file, q_values) # custom file
            break
def receive_human_state():
    global human_state
    with open(input_file) as file:
        try:
            data = json.load(file)
            human_state = data.get(list(data)[-1])
            return human_state
        except ValueError:
            return human_state # return last value
            
# main function
def main():
    global conn_reset
    global conn
    global q_values
    global sock
    global input_file
    global output_file
    argparser = argparse.ArgumentParser(
        description='Q-learning LDW Server')
    argparser.add_argument(
        '-n', '--hostname',
        metavar='HOSTNAME',
        default='localhost',
        help='computer hostname')
    argparser.add_argument(
        '-i', '--input',
        metavar='INPUT',
        default='HumanStates.json',
        help='specify an input JSON file name for human state data (default is HumanStates.json)')
    argparser.add_argument(
        '-o', '--output',
        metavar='OUTPUT',
        default='DriverQValues.npy',
        help='specify the output NumPy file for this driver. If it does not exist, it will be created.')
    args = argparser.parse_args()
    input_file = args.input
    output_file = args.output
    hostname_to_IP = {'iMac': '192.168.0.5', 'MBP': '192.168.0.78', 'MBPo': '192.168.254.41', 'localhost': '127.0.0.1'}
    IP = hostname_to_IP.get(args.hostname)
    port = 50007
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((IP, port))
    sock.listen(1)
    conn, addr = sock.accept()
    print("Connected by", addr)
    thread = threading.Thread(target=ThreadFunction, args=(conn,))
    thread.start()
    if(os.path.exists(output_file)):
        print("\n")
        print("Existing Q-table loaded ...")
        q_values = np.load(output_file)
        np.set_printoptions(suppress=True)
        print(q_values)
    else:
        np.save(output_file, q_values) # custom file
        initialize_q_table()
    try:
        episode = 1
        while(True):
            print("Running episode " + str(episode) + " (" + str(iterations) + " iterations)")
            q_learning(thread)
            print("Episode " + str(episode) + " completed.")
            episode += 1
            print("\n")
        if(conn_reset):
            sock.close()
            conn.close()
            conn_reset = False
            main()
    except EOFError:
        sock.close()
        conn.close()
        thread.join()
        exit()
    except KeyboardInterrupt:
        sock.close()
        conn.close()
        thread.join()
        exit()
    conn.close()
main()
