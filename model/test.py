import torch
import numpy as np
import matplotlib.pyplot as plt
import torchvision
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm

from dataset import accuracy_metric

# Write the test function here!

def test_one_epoch(model, test_loader, device : str):
    #counters for both correct and total predictions
    correct = 0
    total = 0
    with torch.no_grad(): #does not calculate gradients for performance optimization (does not store gradient graphs)
        model.eval() #puts into an evaluation state (drops droput layer and changes normalization layer)
        
        with tqdm(range(len(test_loader))) as pbar:
            for batch_inputs, batch_labels in test_loader:
                batch_inputs, batch_labels = batch_inputs.to(device), batch_labels.to(device)
                batch_outputs = F.sigmoid((batch_inputs)).squeeze()

                correct, total += accuracy_metric(batch_outputs, batch_labels)

                pbar.set_postfix({"acc": f"{round(100 * correct / total, 3):.2f}%"})
                pbar.update()
    
    #calculate and print out accuracy
    accuracy = round(100 * correct / total, 3)
    print(f'Accuracy at end of epoch: {accuracy}%')
    