# Diagnosis-HER
Diagnosis Hindsight Experience Replay (Diagnosis-HER)


#Don't we learn from our every attempt? - Towards Building A Diagnosis Assistant that Learns from Both Successful and Unsuccessful Diagnoses

First, install the environment dependencies using environment.yml

- Location of the main file for running the models : 

    DPL/src/dialogue_system/run/run.py

## Dataset Settings
- To use SD dataset :
    dataset_type = "SD"
    dataset_location = "src/classifier/data/sd_dataset"
    
- To use MD dataset :
    dataset_type = "MD"
    dataset_location = "src/classifier/data/md_dataset"

## DQN Algorithm Settings

- To use DQN algorithm : 
    dqn_type = "DQN"
    
- To use Double DQN algorithm :
    dqn_type = "DoubleDQN"
    
    
## Running different models
- To run Flat-DQN :
    agent_id = "agentdqn"
    disease_as_action = True
    use_all_labels = False
    
- To run HRL : 
    agent_id = "agenthrljoint2"
    allow_wrong_disease = False
    wrong_disease_knowledge = False
    sf_idf_knowledge = False
    disease_as_action = False
    classifier_type = "deep_learning"
    use_all_labels = True

- To run DHER with only Trimming :
    is_trimming_used = True
    is_stitching_used = False
    agent_id = "agenthrljoint2"
    disease_as_action = False
    classifier_type = "deep_learning"

- To run DHER with only Stitching :
    is_trimming_used = False
    is_stitching_used = True
    agent_id = "agenthrljoint2"
    disease_as_action = False
    classifier_type = "deep_learning"
    
 To run DHER :
    is_trimming_used = True
    is_stitching_used = True
    agent_id = "agenthrljoint2"
    disease_as_action = False
    classifier_type = "deep_learning"


For training :
    train_mode = True 

For testing : 
    train_mode = False 
    saved_model = model location (./../../../../src/model/DQN/checkpoint/)
