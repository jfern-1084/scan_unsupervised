"""
Author: Wouter Van Gansbeke, Simon Vandenhende
Licensed under the CC BY-NC 4.0 license (https://creativecommons.org/licenses/by-nc/4.0/)
"""
import os
import torch
import torch.utils.data as data
from PIL import Image
from utils.mypath import MyPath
from torchvision import transforms as tf
from glob import glob
import pandas as pd
from detectron2.data import transforms as T_

main_dir = '/scratch/b/bkantarc/jfern090/Projects/Lytica/'
img_dir = 'Dataset/Images/'
ref_dir = 'Reference/'
output_dir = 'Output/'
model_dir = 'Models/'


class TableDB(data.Dataset):
    def __init__(self, split='train', transform=None):
        file_name = ""
        if split == 'train':
            file_name = main_dir + ref_dir + "train_set1_unsup.csv"
        else:
            file_name = main_dir + ref_dir + "ic13_test_unsup.csv"

        self.csv_file = pd.read_csv(file_name)
        self.transform = transform 
        self.split = split
        self.shortest_size = 912
        self.largest_size = 1600

    def __len__(self):
        return len(self.csv_file)

    def __getitem__(self, index):
        row = self.csv_file.iloc[index]
        path, target, class_name = row[1], row[2], row[3]
        img = Image.open(path)
        width, height = img.size
        scale = self.shortest_size * (1.0 / min(width, height))

        if width < height:
            width, height = self.shortest_size, height * scale
        else:
            width, height = width * scale, self.shortest_size

        if max(width, height) > self.largest_size:
            scale = self.largest_size * 1.0 / max(width, height)
            height = height * scale
            width = width * scale

        width = int(width + 0.5)
        height = int(height + 0.5)

        img = img.resize((width, height))
        im_size = img.size

        if self.transform is not None:
            img = self.transform(img)

        out = {'image': img, 'target': target, 'meta': {'im_size': im_size, 'index': index, 'class_name': class_name}}

        return out

    def get_image(self, index):
        path = self.csv_file.iloc[index, 1]
        img = Image.open(path)
        img = self.resize(img) 
        return img


