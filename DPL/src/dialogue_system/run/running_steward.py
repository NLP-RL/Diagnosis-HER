# -*-coding: utf-8 -*-

import sys
import os
import pickle
import time
import json
from collections import deque
import copy
import math

sys.path.append(os.getcwd().replace("src/dialogue_system/run",""))

from src.dialogue_system.agent import AgentRule
from src.dialogue_system.agent import AgentDQN
from src.dialogue_system.user_simulator import UserRule as User
from src.dialogue_system.dialogue_manager import DialogueManager
from src.dialogue_system.dialogue_manager import DialogueManager_HRL
from src.dialogue_system import dialogue_configuration
#from src.dialogue_system.dialogue_manager import dl_classifier
import random

class RunningSteward(object):
    """
    The steward of running the dialogue system.
    """
    def __init__(self, parameter, checkpoint_path):
        self.epoch_size = parameter.get("simulation_size",100)
        self.parameter = parameter
        self.checkpoint_path = checkpoint_path
        self.learning_curve = {}

        slot_set = pickle.load(file=open(parameter["slot_set"], "rb"))
        action_set = pickle.load(file=open(parameter["action_set"], "rb"))
        goal_set = pickle.load(file=open(parameter["goal_set"], "rb"))
        disease_symptom = pickle.load(file=open(parameter["disease_symptom"], "rb"))

        user = User(goal_set=goal_set, disease_syptom=disease_symptom,parameter=parameter)
        agent = AgentRule(action_set=action_set, slot_set=slot_set, disease_symptom=disease_symptom, parameter=parameter)
        if parameter.get("use_all_labels"):
            self.dialogue_manager = DialogueManager_HRL(user=user, agent=agent, parameter=parameter)
        else:
            self.dialogue_manager = DialogueManager(user=user, agent=agent, parameter=parameter)
        if self.parameter.get("disease_as_action") == False:
            if self.parameter.get("classifier_type") == "machine_learning":
                self.dialogue_manager.train_ml_classifier()
                print("############   the machine learning model is training  ###########")
            elif self.parameter.get("classifier_type") == "deep_learning":
                self.dialogue_manager.build_deep_learning_classifier()
            else:
                raise ValueError("the classifier type is not among machine_learning and deep_learning")


        self.best_result = {"success_rate":0.0, "average_reward": 0.0, "average_turn": 0,"average_wrong_disease":10}

    def simulate(self, epoch_number, train_mode=False):
       
        save_model = self.parameter.get("save_model")
        save_performance = self.parameter.get("save_performance")
        # self.dialogue_manager.state_tracker.user.set_max_turn(max_turn=self.parameter.get('max_turn'))
        for index in range(0, epoch_number,1):
            # Training AgentDQN with experience replay
            if train_mode is True:
                self.dialogue_manager.train()
                # Simulating and filling experience replay pool.
                self.simulation_epoch(epoch_size=self.epoch_size, index=index)

            # Evaluating the model.
            #print(index)
            result = self.evaluate_model(dataset="train", index=index)

            if result["success_rate"] > self.best_result["success_rate"] and \
                    result["success_rate"] > dialogue_configuration.SUCCESS_RATE_THRESHOLD and train_mode==True:
                    #result["average_wrong_disease"] <= self.best_result["average_wrong_disease"] and \
                self.dialogue_manager.state_tracker.agent.flush_pool()
                self.simulation_epoch(epoch_size=self.epoch_size, index=index)
                if save_model is True:
                    self.dialogue_manager.state_tracker.agent.save_model(model_performance=result, episodes_index = index, checkpoint_path=self.checkpoint_path)
                    if self.parameter.get("agent_id").lower() in ["agenthrljoint", "agenthrljoint2",'agentdqn']:
                        self.dialogue_manager.save_dl_model(model_performance=result, episodes_index=index,
                                                            checkpoint_path=self.checkpoint_path)
                    print("###########################The model was saved.###################################")
                else:
                    pass
                self.best_result = copy.deepcopy(result)
        # The training is over and save the model of the last training epoch.
        if save_model is True and train_mode is True and epoch_number > 0:
            self.dialogue_manager.state_tracker.agent.save_model(model_performance=result, episodes_index=index, checkpoint_path=self.checkpoint_path)
            if self.parameter.get("agent_id").lower() in ["agenthrljoint","agenthrljoint2"]:
                self.dialogue_manager.save_dl_model(model_performance=result, episodes_index=index, checkpoint_path=self.checkpoint_path)
        if save_performance is True and train_mode is True and epoch_number > 0:
            self.__dump_performance__(epoch_index=index)

    def simulation_epoch(self, epoch_size, index):
       
        success_count = 0
        absolute_success_count = 0
        total_reward = 0
        total_turns = 0
        self.dialogue_manager.state_tracker.agent.eval_mode() # for testing
        inform_wrong_disease_count = 0
        for epoch_index in range(0,epoch_size, 1):
            self.dialogue_manager.initialize(dataset="train")
            episode_over = False
            while episode_over is False:
                reward, episode_over, dialogue_status,slots_proportion_list= self.dialogue_manager.next(greedy_strategy=True, save_record=True, index=index)
                total_reward += reward
            total_turns += self.dialogue_manager.state_tracker.turn
            inform_wrong_disease_count += self.dialogue_manager.inform_wrong_disease_count
            if dialogue_status == dialogue_configuration.DIALOGUE_STATUS_SUCCESS:
                success_count += 1
                if self.dialogue_manager.inform_wrong_disease_count == 0:
                    absolute_success_count += 1
        success_rate = float("%.3f" % (float(success_count) / epoch_size))
        absolute_success_rate = float("%.3f" % (float(absolute_success_count) / epoch_size))
        average_reward = float("%.3f" % (float(total_reward) / epoch_size))
        average_turn = float("%.3f" % (float(total_turns) / epoch_size))
        average_wrong_disease = float("%.3f" % (float(inform_wrong_disease_count) / epoch_size))
        res = {"success_rate":success_rate, "average_reward": average_reward, "average_turn": average_turn,
               "average_wrong_disease":average_wrong_disease,"ab_success_rate":absolute_success_rate}
        print("%3d simulation success rate %s, ave reward %s, ave turns %s, ave wrong disease %s" % (index,res['success_rate'], res['average_reward'], res['average_turn'], res["average_wrong_disease"]))
        self.dialogue_manager.state_tracker.agent.train_mode() # for training
        return res

    def evaluate_model(self, dataset, index):
       

        if self.parameter.get("train_mode") == False:
            self.dialogue_manager.dialogue_output_file = self.parameter['dialogue_file'] + str(index) + '_dialogue_file.txt'

        if self.parameter.get("use_all_labels"):
            self.dialogue_manager.repeated_action_count = 0
            self.dialogue_manager.group_id_match = 0
        if self.parameter.get("initial_symptom"):
            self.dialogue_manager.group_id_match = 0
        self.dialogue_manager.repeated_action_count = 0
        save_performance = self.parameter.get("save_performance")
        self.dialogue_manager.state_tracker.agent.eval_mode() # for testing
        success_count = 0
        absolute_success_count = 0
        total_reward = 0
        total_turns = 0
        #evaluate_session_number = len(self.dialogue_manager.state_tracker.user.goal_set[dataset])
        dataset_len=len(self.dialogue_manager.state_tracker.user.goal_set[dataset])
        evaluate_session_number=self.parameter.get("evaluate_session_number")

        # If MD dataset is used while testing
        if self.parameter.get("train_mode") == False and self.parameter.get("dataset_type") == "MD":
            evaluate_session_index = list(range(dataset_len))
            evaluate_session_number = len(self.dialogue_manager.state_tracker.user.goal_set[dataset])
        else:
            evaluate_session_index = random.sample(range(dataset_len), evaluate_session_number)
        inform_wrong_disease_count = 0
        num_of_true_slots = 0
        num_of_implicit_slots = 0
        real_implicit_slots = 0
        #for goal_index in range(0,evaluate_session_number, 1):
        for goal_index in evaluate_session_index:
            self.dialogue_manager.initialize(dataset=dataset, goal_index=goal_index)
            episode_over = False
            while episode_over == False:
                reward, episode_over, dialogue_status,slots_proportion_list = self.dialogue_manager.next(
                    save_record=False,greedy_strategy=False, index=index)
                total_reward += reward
            assert len(slots_proportion_list)>0
            num_of_true_slots+=slots_proportion_list[0]
            num_of_implicit_slots+=slots_proportion_list[1]
            real_implicit_slots += slots_proportion_list[2]
            #(slots_proportion_list)
            total_turns += self.dialogue_manager.state_tracker.turn
            inform_wrong_disease_count += self.dialogue_manager.inform_wrong_disease_count
            if dialogue_status == dialogue_configuration.DIALOGUE_STATUS_SUCCESS:
                success_count += 1
                if self.dialogue_manager.inform_wrong_disease_count == 0:
                    absolute_success_count += 1
        success_rate = float("%.3f" % (float(success_count) / evaluate_session_number))
        absolute_success_rate = float("%.3f" % (float(absolute_success_count) / evaluate_session_number))
        average_reward = float("%.3f" % (float(total_reward) / evaluate_session_number))
        average_turn = float("%.3f" % (float(total_turns) / evaluate_session_number))
        average_wrong_disease = float("%.3f" % (float(inform_wrong_disease_count) / evaluate_session_number))
        match_rate2 = float("%.3f" % (float(num_of_true_slots) / float(real_implicit_slots)))
        if num_of_implicit_slots>0:
            #match rate表示agent所问道的症状当中是病人确实有的概率为多大。match rate2表示病人有多少比例的隐形症状被agent问出。
            match_rate=float("%.3f" %(float(num_of_true_slots)/float(num_of_implicit_slots)))
        else:
            match_rate=0.0
        average_repeated_action = float("%.4f" % (float(self.dialogue_manager.repeated_action_count) / evaluate_session_number))

        self.dialogue_manager.state_tracker.agent.train_mode() # for training.
        res = {
            "success_rate":success_rate,
            "average_reward": average_reward,
            "average_turn": average_turn,
            "average_repeated_action": average_repeated_action,
            "average_match_rate2": match_rate2,
            "ab_success_rate":absolute_success_rate,
            "average_match_rate":match_rate
        }
        self.learning_curve.setdefault(index, dict())
        self.learning_curve[index]["success_rate"]=success_rate
        self.learning_curve[index]["average_reward"]=average_reward
        self.learning_curve[index]["average_turn"] = average_turn
        #self.learning_curve[index]["average_wrong_disease"]=average_wrong_disease
        self.learning_curve[index]["average_match_rate"]=match_rate
        self.learning_curve[index]["average_match_rate2"] = match_rate2
        self.learning_curve[index]["average_repeated_action"] = average_repeated_action
        if index % 10 ==9:
            print('[INFO]', self.parameter["run_info"])
        if self.parameter.get("classifier_type")=="deep_learning" and self.parameter.get("disease_as_action") == False:
            self.dialogue_manager.train_deep_learning_classifier(epochs=20)

        if index % 1000 == 999 and save_performance == True:
            self.__dump_performance__(epoch_index=index)
        print("%3d simulation SR [%s], ave reward %s, ave turns %s, ave match rate %s, ave match rate2 %s, ave repeated %s" % (index,res['success_rate'],res['average_reward'], res['average_turn'], res["average_match_rate"],res[ "average_match_rate2"],res["average_repeated_action"]))

        if self.parameter.get("use_all_labels") == True and self.parameter.get("disease_as_action") == False:
            #self.dialogue_manager.train_deep_learning_classifier(epochs=100)

            if self.parameter.get("agent_id").lower() == "agenthrljoint":
                temp_by_group = {}
                for key,value in self.dialogue_manager.acc_by_group.items():
                    temp_by_group[key] = [0.0, 0.0]
                    if value[1] > 0:
                        temp_by_group[key][0] = float("%.3f" % (value[0]/value[1]))
                        temp_by_group[key][1] = float("%.3f" % (value[1]/value[2]))
                if index % 10 == 9:
                    #self.dialogue_manager.train_deep_learning_classifier(epochs=20)
                    print(self.dialogue_manager.acc_by_group)
                    print(temp_by_group)
                self.dialogue_manager.acc_by_group = {x: [0, 0, 0] for x in self.dialogue_manager.state_tracker.agent.master_action_space}

        if self.parameter.get("train_mode") == False and index == self.parameter.get("simulate_epoch_number") - 1:
            metrics = ["success_rate", "average_turn", "average_match_rate", "average_match_rate2"]
            average_values = {}
            for metric in metrics:
                average_values[metric] = {"mean": 0.0, "standard_deviation": 0.0, "standard_error": 0.0}

            for metric in metrics:
                for i in range(0, self.parameter.get("simulate_epoch_number")):
                    if metric == "average_turn":
                        average_values[metric]["mean"] += (self.learning_curve[i][metric]/2)
                    else:
                        average_values[metric]["mean"] += self.learning_curve[i][metric]
                average_values[metric]["mean"] /= 5
                for i in range(0, self.parameter.get("simulate_epoch_number")):
                    if metric == "average_turn":
                        average_values[metric]["standard_deviation"] += (((self.learning_curve[i][metric]/2) - average_values[metric]["mean"]) ** 2)
                    else:
                        average_values[metric]["standard_deviation"] += (((self.learning_curve[i][metric]) - average_values[metric]["mean"]) ** 2)

                average_values[metric]["standard_deviation"] = math.sqrt(average_values[metric]["standard_deviation"] / 4)
                average_values[metric]["standard_error"] = average_values[metric]["standard_deviation"] / math.sqrt(5)
                print("Metric : {}, Mean : {}, SD : {}, SE : {}".format(metric, average_values[metric]["mean"], average_values[metric]["standard_deviation"], 
                                   average_values[metric]["standard_error"]))
            
            disease_classifier_acc = copy.deepcopy(self.dialogue_manager.dc_accuracy)
            mean_acc = sum(disease_classifier_acc) / len(disease_classifier_acc)
            sd_acc = 0.0
            for a in disease_classifier_acc:
                sd_acc += ((a - mean_acc) ** 2)
            sd_acc = math.sqrt(sd_acc / (len(disease_classifier_acc) - 1))
            se_acc = sd_acc / math.sqrt(len(disease_classifier_acc))

            print("Metric : disease classifier acc, Mean : {}, SD : {}, SE : {}".format(mean_acc, sd_acc, se_acc))

            top_k_metrics = ['1', '2', '3', '4', '5']
            top_k_average_accuracy = {}

            for metric in top_k_metrics:
                accuracy_list = []
                
                #print(evaluate_session_number, metric, len(self.dialogue_manager.top_k_disease_record[metric]))
                for test_case_index in range(0, self.parameter.get("simulate_epoch_number") * evaluate_session_number, evaluate_session_number):
                    disease_record = copy.deepcopy(self.dialogue_manager.top_k_disease_record[metric][test_case_index:test_case_index+evaluate_session_number])
                    #print(test_case_index, len(disease_record))
                    success_count = 0
                    total_count = 0
                    for record in disease_record:
                        true_disease = record[0]
                        predicted_diseases = record[1:]
                        if true_disease in predicted_diseases:
                            success_count += 1
                        total_count += 1
                    accuracy_list.append(success_count / total_count)
                top_k_average_accuracy[metric] = copy.deepcopy(accuracy_list)
                #print(accuracy_list)

            for metric in top_k_metrics:
                mean_acc = sum(top_k_average_accuracy[metric]) / len(top_k_average_accuracy[metric])
                sd_acc = 0.0
                se_acc = 0.0
                for element in top_k_average_accuracy[metric]:
                    sd_acc += ((element - mean_acc) ** 2)
                sd_acc = math.sqrt(sd_acc / (len(top_k_average_accuracy[metric]) - 1))
                se_acc = sd_acc / math.sqrt(len(top_k_average_accuracy[metric]))
                 
                print("Top - {} disease classifier acc, Mean : {}, SD : {}, SE : {}".format(metric, mean_acc, sd_acc, se_acc))

        if self.parameter.get("use_all_labels") == True and self.parameter.get("agent_id").lower() in ["agenthrljoint", "agenthrljoint2"] and self.parameter.get('train_mode') == False:
            pickle.dump(self.dialogue_manager.disease_record, open(self.parameter.get("path_for_disease_record_storage") + 'disease_record.p', 'wb'))
            pickle.dump(self.dialogue_manager.lower_reward_by_group, open(self.parameter.get("path_for_disease_record_storage") + 'lower_reward_by_group.p', 'wb'))
            pickle.dump(self.dialogue_manager.master_index_by_group, open(self.parameter.get("path_for_disease_record_storage") + 'master_index_by_group.p', 'wb'))
            pickle.dump(self.dialogue_manager.symptom_by_group, open(self.parameter.get("path_for_disease_record_storage") + 'symptom_by_group.p', 'wb'))
            print("##################   the disease record is saved   #####################")

        if self.parameter.get("use_all_labels") and self.parameter.get("agent_id").lower()=="agenthrlnew2" and self.parameter.get("disease_as_action"):
            print("the group id match is %f"%(int(self.dialogue_manager.group_id_match) / int(evaluate_session_number)))
            self.dialogue_manager.group_id_match = 0
            if self.parameter.get("train_mode")==False:
                test_by_group = {key:float(x[0])/float(x[1]) for key,x in self.dialogue_manager.test_by_group.items()}
                print(self.dialogue_manager.test_by_group)
                print(test_by_group)
                self.dialogue_manager.test_by_group = {x:[0,0,0] for x in self.dialogue_manager.state_tracker.agent.master_action_space}
        return res

    def warm_start(self, epoch_number):
       
        for index in range(0,epoch_number,1):
            res = self.simulation_epoch(epoch_size=self.epoch_size, index=index)
            print("%3d simulation SR %s, ABSR %s,ave reward %s, ave turns %s, ave wrong disease %s" % (
            index, res['success_rate'], res["ab_success_rate"], res['average_reward'], res['average_turn'], res["average_wrong_disease"]))
          k

    def __dump_performance__(self, epoch_index):
       
        file_name = self.parameter["run_info"] + "_" + str(epoch_index) + ".p"
        performance_save_path = self.parameter["performance_save_path"]
        if os.path.isdir(performance_save_path) is False:
            os.mkdir(performance_save_path)
        
        pickle.dump(file=open(os.path.join(performance_save_path,file_name), "wb"), obj=self.learning_curve)
