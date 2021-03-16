"""
Authors: Wouter Van Gansbeke, Simon Vandenhende
Licensed under the CC BY-NC 4.0 license (https://creativecommons.org/licenses/by-nc/4.0/)
"""
import argparse
import os
import torch
import torch.nn.functional as F
import numpy as np
from tqdm import tqdm

from utils.config import create_config
from utils.common_config import get_criterion, get_model, get_train_dataset, \
    get_val_dataset, get_train_dataloader, \
    get_val_dataloader, get_train_transformations, \
    get_val_transformations, get_optimizer, \
    adjust_learning_rate
from utils.evaluate_utils import contrastive_evaluate
from utils.memory import MemoryBank
from utils.train_utils import simclr_train
from utils.utils import fill_memory_bank
from termcolor import colored

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Parser
parser = argparse.ArgumentParser(description='SimCLR')
parser.add_argument('--config_env',
                    help='Config file for the environment')
parser.add_argument('--config_exp',
                    help='Config file for the experiment')
args = parser.parse_args()


# knn monitor as in InstDisc https://arxiv.org/abs/1805.01978
# implementation follows http://github.com/zhirongw/lemniscate.pytorch and https://github.com/leftthomas/SimCLR
def knn_predict(feature, feature_bank, feature_labels, classes, knn_k, knn_t):
    # # compute cos similarity between each feature vector and feature bank ---> [B, N]
    # sim_matrix = torch.mm(feature, feature_bank)
    # # [B, K]
    # sim_weight, sim_indices = sim_matrix.topk(k=knn_k, dim=-1)
    # # [B, K]
    # sim_labels = torch.gather(feature_labels.expand(feature.size(0), -1), dim=-1, index=sim_indices)
    # sim_weight = (sim_weight / knn_t).exp()
    #
    # # counts for each class
    # one_hot_label = torch.zeros(feature.size(0) * knn_k, classes, device=sim_labels.device)
    # # [B*K, C]
    # one_hot_label = one_hot_label.scatter(dim=-1, index=sim_labels.view(-1, 1), value=1.0)
    # # weighted score ---> [B, C]
    # pred_scores = torch.sum(one_hot_label.view(feature.size(0), -1, classes) * sim_weight.unsqueeze(dim=-1), dim=1)
    #
    # pred_labels = pred_scores.argsort(dim=-1, descending=True)
    # return pred_labels

    # compute cos similarity between each feature vector and feature bank ---> [B, N]
    sim_matrix = torch.mm(feature, feature_bank)
    # [B, K]
    sim_weight, sim_indices = sim_matrix.topk(k=knn_k, dim=-1)
    # # [B, K]
    # sim_labels = torch.gather(feature_labels.expand(feature.size(0), -1), dim=-1, index=sim_indices)
    # sim_weight = (sim_weight / knn_t).exp()
    #
    # # counts for each class
    # one_hot_label = torch.zeros(feature.size(0) * knn_k, classes, device=sim_labels.device)
    # # [B*K, C]
    # one_hot_label = one_hot_label.scatter(dim=-1, index=sim_labels.view(-1, 1), value=1.0)
    # # weighted score ---> [B, C]
    # pred_scores = torch.sum(one_hot_label.view(feature.size(0), -1, classes) * sim_weight.unsqueeze(dim=-1), dim=1)
    #
    # pred_labels = pred_scores.argsort(dim=-1, descending=True)
    return sim_indices


def main():
    # Retrieve config file
    p = create_config(args.config_env, args.config_exp)
    print(colored(p, 'red'))

    # Model
    print(colored('Retrieve model', 'green'))
    model = get_model(p)
    print('Model is {}'.format(model.__class__.__name__))
    print('Model parameters: {:.2f}M'.format(sum(p.numel() for p in model.parameters()) / 1e6))
    print(model)
    model = model.to(device)

    # CUDNN
    print(colored('Set CuDNN benchmark', 'green'))
    torch.backends.cudnn.benchmark = True

    # Dataset
    print(colored('Retrieve dataset', 'green'))
    train_transforms = get_train_transformations(p)
    print('Train transforms:', train_transforms)
    val_transforms = get_val_transformations(p)
    print('Validation transforms:', val_transforms)
    train_dataset = get_train_dataset(p, train_transforms, to_augmented_dataset=True,
                                      split='train')  # Split is for stl-10
    val_dataset = get_val_dataset(p, val_transforms)
    train_dataloader = get_val_dataloader(p, train_dataset)
    # val_dataloader = get_val_dataloader(p, val_dataset)
    print('Dataset contains {}/{} train/val samples'.format(len(train_dataset), len(val_dataset)))



    # Checkpoint
    if os.path.exists(p['pretext_checkpoint']):
        print(colored('Restart from checkpoint {}'.format(p['pretext_checkpoint']), 'green'))
        checkpoint = torch.load(p['pretext_checkpoint'], map_location='cpu')
        # optimizer.load_state_dict(checkpoint['optimizer'])
        model.load_state_dict(checkpoint['model'])
        model.to(device)
        # start_epoch = checkpoint['epoch']

    else:
        print(colored('No checkpoint file at {}'.format(p['pretext_checkpoint']), 'green'))
        start_epoch = 0
        model = model.to(device)

    # Training
    print(colored('Starting main loop', 'green'))
    with torch.no_grad():
        model.eval()
        total_top1, total_top5, total_num, feature_bank = 0.0, 0.0, 0, []

        # progress_bar = tqdm(train_dataloader)
        for idx, batch in enumerate(train_dataloader):
            images = batch['image'].to(device, non_blocking=True)
            # target = batch['target'].to(device, non_blocking=True)

            output = model(images)
            feature = F.normalize(output, dim=1)
            feature_bank.append(feature)

            if idx % 25 == 0:
                print("Feature bank buidling : {} / {}".format(idx, len(train_dataset)/p["batch_size"]))

        # [D, N]
        feature_bank = torch.cat(feature_bank, dim=0).t().contiguous()
        print(colored("Feature bank created. Similarity index starts now", "green"))
        print(feature_bank.size())

        for batch in train_dataloader:

            images = batch['image'].to(device, non_blocking=True)
            # target = batch['target'].to(device, non_blocking=True)

            output = model(images)
            feature = F.normalize(output, dim=1)

            sim_indices = knn_predict(feature, feature_bank, "", "", 10, 0.1)

            print(sim_indices)

if __name__ == '__main__':
    main()