"""Handle basic dataset creation.

In case of PyTorch it should return dataloaders for your dataset (for both the clients
and the server). If you are using a custom dataset class, this module is the place to
define it. If your dataset requires to be downloaded (and this is not done
automatically -- e.g. as it is the case for many dataset in TorchVision) and
partitioned, please include all those functions and logic in the
`dataset_preparation.py` module. You can use all those functions from functions/methods
defined here of course.
"""

import numpy as np
from torch.utils.data import DataLoader, Dataset
from omegaconf import DictConfig
from typing import Optional, Tuple
from dataset_preparation import _partition_data, split_train_validation_test_clients
import numpy as np
from torch.utils.data import DataLoader
import torchvision.transforms as transforms



class FemnistDataset(Dataset):
    def __init__(self, dataset, transform):
        self.x = dataset['x']
        self.y = dataset['y']
        self.transform = transform

    def __getitem__(self, index):
        input_data = np.array(self.x[index]).reshape(28, 28, 1)
        if self.transform:
            input_data = self.transform(input_data)
        target_data = self.y[index]
        return input_data, target_data

    def __len__(self):
        return len(self.y)


def load_datasets(  # pylint: disable=too-many-arguments
    config: DictConfig,
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    print(f"Dataset partitioning config: {config}")

    dataset = _partition_data(
        dir_path=config.path,
        support_ratio=config.support_ratio
    )

    clients_list = split_train_validation_test_clients(
        dataset[0]['users']
    )

    trainloaders = {'sup': [], 'qry': []}
    valloaders = {'sup': [], 'qry': []}
    testloaders = {'sup': [], 'qry': []}

    transform = transforms.Compose([transforms.ToTensor()])
    for user in clients_list[0]:
        trainloaders['sup'].append(DataLoader(FemnistDataset(dataset[0]['user_data'][user], transform), batch_size=10, shuffle=True))
        trainloaders['qry'].append(DataLoader(FemnistDataset(dataset[1]['user_data'][user], transform), batch_size=10))
    for user in clients_list[2]:
        valloaders['sup'].append(DataLoader(FemnistDataset(dataset[0]['user_data'][user], transform), batch_size=10, shuffle=True))
        valloaders['qry'].append(DataLoader(FemnistDataset(dataset[1]['user_data'][user], transform), batch_size=10))
    for user in clients_list[1]:
        testloaders['sup'].append(DataLoader(FemnistDataset(dataset[0]['user_data'][user], transform), batch_size=10, shuffle=True))
        testloaders['qry'].append(DataLoader(FemnistDataset(dataset[1]['user_data'][user], transform), batch_size=10))

    return trainloaders, valloaders, testloaders



