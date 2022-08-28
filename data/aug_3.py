import numpy as np
import os 
import glob
from PIL import Image
import pandas as pd
import json
import cv2
from pathlib import Path
import random 
########################################################################
## For each video, create subvideos with various lengths and start_frame
## {
##    "id": "a01-0",  // The id of the created subvideos
##    "video_name": "a01",  // The original video name
##    "start_frame": 0,   // The start frame annotated in the original video
##    "end_frame": 20,    // The end frame annotated in the original video
##    "middle_frames": [6, 8, 11, 13] // The randomly selected frames between start_jump & end_jump
##    "start_jump": 5,
##    "end_jump": 15
## }
########################################################################
csv_file='/home/lin10/projects/SkatingJumpClassifier/data/all_jump/info.csv'
root_dir='/home/lin10/projects/SkatingJumpClassifier/data/all_jump/train'
videos = list(Path(root_dir).glob("*/"))
jump_frame = pd.read_csv(csv_file, na_values=["None"])
data = []

for video in videos:
    id = 0
    video_name = Path(video).parts[-1]
    frames = list(Path(f'{root_dir}/{video_name}').glob("*.jpg"))
    video_data = jump_frame.loc[jump_frame['Video'] == video_name]
    if video_data.empty:
        continue
    print("==================")
    print("video name:", video_name)

    if not (video_data['start_jump_2'].item() > 0):
    ### 1 Jump
        start_jump = int(video_data['start_jump_1'])
        end_jump = int(video_data['end_jump_1'])
        last_frame = sorted([int(os.path.split(frame)[1].replace('.jpg','')) for frame in frames])[-1]

        #### Orignial videos
        d = {
            "id": f'{video_name}-{id}',
            "video_name": video_name,
            "start_frame": 0,
            "end_frame": last_frame,
            "start_jump_1": start_jump,
            "end_jump_1": end_jump,
            "start_jump_2": -1,
            "end_jump_2": -1
        }
        data.append(d)
        id += 1      
            
        #### REVISED Augmentation_3:
        #### 0 < possible start_frame <= (start_jump - 30)
        #### (end_jump + 30) <= possible end_frame < original end_frame
        for i in range(1, start_jump - 30 + 1, 5):
            start_frame = 0 if i <= 0 else i
            for j in range(end_jump + 30, last_frame, 5):
                end_frame = last_frame if j >= last_frame else j
                if start_frame == 0 and end_frame == last_frame:
                    continue
                else:
                    d = {
                        "id": f'{video_name}-{id}',
                        "video_name": video_name,
                        "start_frame":start_frame,
                        "end_frame": end_frame,
                        "start_jump_1": start_jump,
                        "end_jump_1": end_jump,
                        "start_jump_2": -1,
                        "end_jump_2": -1
                    }
                    data.append(d)
                    id += 1
    #### TWO JUMPS
    else:
        #### calculate the air_length
        start_jump_1 = int(video_data['start_jump_1'])
        end_jump_1 = int(video_data['end_jump_1'])
        start_jump_2 = int(video_data['start_jump_2'])
        end_jump_2 = int(video_data['end_jump_2'])
        last_frame = sorted([int(os.path.split(frame)[1].replace('.jpg','')) for frame in frames])[-1]

        #### Orignial videos
        d = {
            "id": f'{video_name}-{id}',
            "video_name": video_name,
            "start_frame": 0,
            "end_frame": last_frame,
            "start_jump_1": start_jump_1,
            "end_jump_1": end_jump_1,
            "start_jump_2": start_jump_2,
            "end_jump_2": end_jump_2
        }
        data.append(d)
        id += 1

        #### Only the first jump (end_frame cannot exceed start_jump_2)
        for i in range(1, start_jump_1 - 30 + 1, 5):
            start_frame = 0 if i < 0 else i
            for j in range(end_jump_1 + 30, last_frame, 5):
                end_frame = -1 if (j >= start_jump_2) else j
                if (start_frame == 0 or end_frame == -1):
                    continue
                else:
                    d = {
                        "id": f'{video_name}-{id}',
                        "video_name": video_name,
                        "start_frame":start_frame,
                        "end_frame": end_frame,
                        "start_jump_1": start_jump_1,
                        "end_jump_1": end_jump_1,
                        "start_jump_2": -1,
                        "end_jump_2": -1
                    }
                    data.append(d)
                    id += 1
        #### Only the second jump (start_frame cannot be less than end_jump_1)
        for i in range(1, start_jump_2 - 30 + 1, 5):
            start_frame = -1 if i < end_jump_1 else i
            if end_jump_2 + 30 > last_frame:
                end_frame = last_frame
                if start_frame == -1:
                    continue
                else:
                    d = {
                        "id": f'{video_name}-{id}',
                        "video_name": video_name,
                        "start_frame":start_frame,
                        "end_frame": end_frame,
                        "start_jump_1": start_jump_2,
                        "end_jump_1": end_jump_2,
                        "start_jump_2": -1,
                        "end_jump_2": -1
                    }
                    data.append(d)
                    id += 1
            else:
                for j in range(end_jump_2 + 30, last_frame, 5):
                    end_frame = last_frame if (j >= last_frame) else j
                    if start_frame == -1 or end_frame == last_frame:
                        continue
                    else:
                        d = {
                            "id": f'{video_name}-{id}',
                            "video_name": video_name,
                            "start_frame":start_frame,
                            "end_frame": end_frame,
                            "start_jump_1": start_jump_2,
                            "end_jump_1": end_jump_2,
                            "start_jump_2": -1,
                            "end_jump_2": -1
                        }
                        data.append(d)
                        id += 1

        ### augmentations that contain 2 jumps
        for i in range(1, start_jump_1 - 30 + 1, 5):
            start_frame = 0 if (i <= 0) else i
            for j in range(end_jump_2 + 30, last_frame, 5):
                end_frame = last_frame if (j >= last_frame) else j
                if start_frame == 0 and end_frame == last_frame:
                    continue
                else:
                    d = {
                        "id": f'{video_name}-{id}',
                        "video_name": video_name,
                        "start_frame":start_frame,
                        "end_frame": end_frame,
                        "start_jump_1": start_jump_1,
                        "end_jump_1": end_jump_1,
                        "start_jump_2": start_jump_2,
                        "end_jump_2": end_jump_2
                    }
                    data.append(d)
                    id += 1
print(len(data))

json_file = '/home/lin10/projects/SkatingJumpClassifier/data/all_jump/train_aug3.jsonl'
with open(os.path.join(json_file), "w") as f:
    for d in data:
        json.dump(d, f)
        f.write('\n')