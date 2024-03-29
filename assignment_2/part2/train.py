################################################################################
# MIT License
#
# Copyright (c) 2017 Tom Runia
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to conditions.
#
# Author: Deep Learning Course | Fall 2018
# Date Created: 2018-09-04
################################################################################

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import time
from datetime import datetime
import argparse

import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from dataset import TextDataset
from model import TextGenerationModel

################################################################################

def generate_sentence(model, dataset, length, first_char, device, temp):

    sentence = []

    out, h, c = model(first_char)

    for _ in range(length):

        char = torch.zeros(1, 1, dataset.vocab_size)
        char[0, 0, out.argmax().item()] = 1
        char = char.to(device)

        out, h, c = model.generate_character(char, h, c)

        if temp == None:
            sentence.append(out.argmax().item())
        else:
            d = torch.softmax(out.squeeze() / temp, dim=0)
            sentence.append(torch.multinomial(d, 1).item())

    return dataset.convert_to_string(sentence)


def train(config):

    # Initialize the device which to run the model on
    device = torch.device(config.device)
    print('device used:', device)

    # Initialize the dataset and data loader (note the +1)
    dataset = TextDataset(config.txt_file, config.seq_length)
    data_loader = DataLoader(dataset, config.batch_size, num_workers=1)

    # Initialize the model that we are going to use
    model = TextGenerationModel(config.batch_size, config.seq_length, \
                                dataset.vocab_size, \
                                lstm_num_hidden=config.lstm_num_hidden, \
                                lstm_num_layers=config.lstm_num_layers, \
                                device=config.device)

    # Setup the loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.RMSprop(model.parameters(), lr=config.learning_rate)

    sentences = 'book used:' + config.txt_file
    accuracies = 'book used:' + config.txt_file + '\n'

    for epoch in range(config.epochs):

        sentences += '\n epoch: ' + str(epoch)
        for step, (batch_inputs, batch_targets) in enumerate(data_loader):

            # Only for time measurement of step through network
            t1 = time.time()

            #######################################################
            # Add more code here ...
            #######################################################

            batch_size = batch_inputs[0].size(0)

            x_batch = torch.zeros(config.seq_length, batch_size, \
                                  dataset.vocab_size)
            x_batch.scatter_(2, torch.stack(batch_inputs).unsqueeze_(-1), 1)
            x_batch = x_batch.to(device)
            y_batch = torch.stack(batch_targets).to(device)

            optimizer.zero_grad()
            nn_out, _, _ = model(x_batch)
            loss = criterion(nn_out.view(-1, dataset.vocab_size), \
                             y_batch.view(-1))
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), \
                                     max_norm=config.max_norm)
            optimizer.step()

            accuracy = (torch.argmax(nn_out, dim=2) == y_batch).sum().item()\
                        / (batch_size * config.seq_length)

            # Just for time measurement
            t2 = time.time()
            examples_per_second = config.batch_size/float(t2-t1)

            if step % config.print_every == 0:

                print("[{}] Train Step {:04d}/{:04d}, Batch Size = {},\
                       Examples/Sec = {:.2f}, "
                      "Accuracy = {:.2f}, Loss = {:.3f}".format(
                        datetime.now().strftime("%Y-%m-%d %H:%M"), step,
                        config.train_steps, config.batch_size, \
                        examples_per_second, accuracy, loss
                ))
                accuracies += str(accuracy) + ", "

            if step % config.sample_every == 0:
                # Generate some sentences by sampling from the model
                char = torch.zeros(1, 1, dataset.vocab_size)
                char[0, 0, np.random.randint(0, dataset.vocab_size)] = 1
                char = char.to(device)
                sentence = generate_sentence(model, dataset, config.seq_length,\
                                             char, device, config.temp)
                sentences += '\n' + str(step) + ' | ' + sentence
                print(sentence)

            if step == config.train_steps:
                # If you receive a PyTorch data-loader error, check this bug report:
                # https://github.com/pytorch/pytorch/pull/9655
                break

    print('Done training.')

    with open('sentences/' + config.txt_file[7:] + 'temp' + str(config.temp), 'w') as f:
        f.write(sentences)
    with open('accuracies/' + config.txt_file[7:] + 'temp' + str(config.temp), 'w') as f:
        f.write(accuracies)


 ###############################################################################
 ###############################################################################

if __name__ == "__main__":

    # Parse training configuration
    parser = argparse.ArgumentParser()

    # to run on normal pc
    parser.add_argument('--device', type=str, default="cuda:0",
                        help="Training device 'cpu' or 'cuda:0'")

    # Model params
    parser.add_argument('--txt_file', type=str, required=True, \
                        help="Path to a .txt file to train on")
    parser.add_argument('--seq_length', type=int, default=30, \
                        help='Length of an input sequence')
    parser.add_argument('--lstm_num_hidden', type=int, default=128, \
                        help='Number of hidden units in the LSTM')
    parser.add_argument('--lstm_num_layers', type=int, default=2, \
                        help='Number of LSTM layers in the model')

    # Training params
    parser.add_argument('--batch_size', type=int, default=64, \
                        help='Number of examples to process in a batch')
    parser.add_argument('--learning_rate', type=float, default=2e-3, \
                        help='Learning rate')
    parser.add_argument('--epochs', type=int, default=1, \
                        help='Number of epochs')

    # It is not necessary to implement the following three params,
    # but it may help training.
    parser.add_argument('--learning_rate_decay', type=float, default=0.96, \
                        help='Learning rate decay fraction')
    parser.add_argument('--learning_rate_step', type=int, default=5000, \
                        help='Learning rate step')
    parser.add_argument('--dropout_keep_prob', type=float, default=1.0, \
                        help='Dropout keep probability')

    parser.add_argument('--train_steps', type=int, default=100, \
                        help='Number of training steps')
    parser.add_argument('--max_norm', type=float, default=5.0, \
                        help='--')

    # Misc params
    parser.add_argument('--summary_path', type=str, default="./summaries/", \
                        help='Output path for summaries')
    parser.add_argument('--print_every', type=int, default=5, \
                        help='How often to print training progress')
    parser.add_argument('--sample_every', type=int, default=100, \
                        help='How often to sample from the model')
    parser.add_argument('--temp', type=float, default=None, \
                        help='Temperature of text generator')

    config = parser.parse_args()

    # Train the model
    train(config)
