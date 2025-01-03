import torch
from torch.utils.data import Dataset
from torchvision.transforms import v2
import os
from PIL import Image

# for determining which dataset to use as specified by the user
import numpy as np
from config import TrainingConfig, enum_names_to_values
from model import ModelTypes


from config import DatasetTypes

def accuracy_metric(predicted_classes, labels):
    correct_predictions = (predicted_classes == labels).sum().item()

    return correct_predictions, labels.size(0)


# returns a list of class accuracies
def per_class_accuracy_metric(predictions, labels):
    # this is a list of lists
    accuracies = []
    sorted_predictions, sorted_labels = sort_images(predictions, labels)

    for prediction, label in zip(sorted_predictions, sorted_labels):
        if label:
            prediction_tensor = torch.tensor(prediction)
            label_tensor = torch.tensor(label)
            accuracies.append((accuracy_metric(prediction_tensor, label_tensor)))
        else:
            accuracies.append((0, 0)) #empty case
    return accuracies       
 
def sort_images(predictions, labels):
    # sorted_sets = [[] for i in range(7)] #init 7 sublists for each data class
    sorted_predictions = [[] for i in range(7)]
    sorted_labels = [[] for i in range(7)]

    for prediction, label in zip(predictions, labels):
        for type, idx in DatasetTypes.items():
            if label & type.value:
                sorted_predictions[idx].append(prediction)
                sorted_labels[idx].append(label)
    return sorted_predictions, sorted_labels


class resize_images(object):
    def __init__(self, target_size=(128, 128)):
        self.target_size = target_size

    def __call__(self, img):
        """
        :param img: (PIL): Image
        """
        padding = (
            max(0, (self.target_size[0] - img.height) // 2),
            max(0, (self.target_size[1] - img.width) // 2),
            max(0, (self.target_size[0] - img.height + 1) // 2),
            max(0, (self.target_size[1] - img.width + 1) // 2),
        )
        transform = v2.Compose(
            [
                v2.Pad(padding=padding, fill=0, padding_mode="constant"),
                v2.CenterCrop(self.target_size),
            ]
        )
        return transform(img)

    def __repr__(self):
        return self.__class__.__name__ + "(target_size={})".format(self.target_size)


class extract_lsb_transform(object):
    def __call__(self, tensor):
        return tensor & 1

    def __repr__(self):
        return self.__class__.__name__


def is_color_channel_image(file_path, color_channel):
    try:
        with Image.open(file_path) as img:
            return img.mode == color_channel
    except IOError:
        return False


class Data(Dataset):
    def __init__(
        self,
        extract_lsb,
        dataset_types: list[int],
        filepath,
        mode,
        color_channel="rgb",
        down_sample_size: None | int = None,
        image_size = 256
    ):
        mode = mode.lower()
        color_channel = color_channel.upper()

        assert (
            down_sample_size >= 1 if down_sample_size is not None else True
        ), f"{down_sample_size} is too small"
        assert mode in ["val", "test", "train"], f"{mode} is not a valid dataset mode"
        assert color_channel in [
            "L",
            "RGB",
            "RGBA",
        ], f"{color_channel} is not a valid color channel"

        self.extract_lsb = extract_lsb

        # moving optional parameters to map
        path_to_folder = {
            DatasetTypes.CLEAN: "clean",
            DatasetTypes.DCT: "DCT",
            DatasetTypes.FFT: "FFT",
            DatasetTypes.LSB: "LSB",
            DatasetTypes.PVD: "PVD",
            DatasetTypes.SSB4: "SSB4",
            DatasetTypes.SSBN: "SSBN",
        }

        filepaths = []
        self.class_labels = []

        # file path identification/appendage, filepath contains 7 lists for each set
        for type in dataset_types:
            self.class_labels.append(path_to_folder[type])  # put all in labels
            folder = path_to_folder.get(type) + mode.capitalize()
            data_classes_paths = [
                os.path.join(filepath, folder, file)
                for file in os.listdir(path=os.path.join(filepath, folder))
            ]
            if down_sample_size is not None:
                data_classes_paths = data_classes_paths[:down_sample_size]

            filepaths.append(data_classes_paths)

        self.all_files = []
        self.dataset_sizes = []
        self.labels = []
        # construct labels and the file dataset
        for n, path in enumerate(filepaths):
            self.all_files.extend(path)
            self.labels.extend([n] * len(path))
            self.dataset_sizes.append(len(path))

        self.labels = torch.tensor(self.labels, dtype=torch.long)

        self.transform = v2.Compose(
            [
                resize_images((image_size, image_size)),
                v2.ToImage(),  # does not scale values
                extract_lsb_transform() if self.extract_lsb else lambda x: x,
                v2.ToDtype(
                    torch.float32
                ),  # preserves original values, no normalize (scale=false default)
            ]
        )

    # return length of dataset
    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        # open in PIL
        filepath = self.all_files[idx]
        # find filepath previosuly
        image = Image.open(filepath)  # directly convert to 32-bit float
        image = self.transform(image)
        # get label
        label = self.labels[idx]

        return image, label


def get_datasets(config):
    converted_dataset_types = enum_names_to_values(config.dataset_types)
    train_dataset = Data(
        config.extract_lsb,
        converted_dataset_types,
        filepath=os.path.join("data", "train"),
        mode="train",
        down_sample_size=config.down_sample_size_train
    )
    test_dataset = Data(
        config.extract_lsb,
        converted_dataset_types,
        filepath=os.path.join("data", "test"),
        mode="test",
        down_sample_size=config.down_sample_size_test
    )
   
    return train_dataset, test_dataset


if __name__ == "__main__":

    config = TrainingConfig(
        epochs=10,
        learning_rate=1e-3,
        model_type=ModelTypes.EfficientNet,
        device= "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu",
        transfer_learning=True,
        extract_lsb=False,
        batch_size=256,
        dataset_types=("CLEAN", "DCT", "FFT", "LSB", "PVD"),
        down_sample_size_train= None,
        down_sample_size_test= None
    )

    train_dataset, test_dataset = get_datasets(config)

    val_dataset = Data(
        config.extract_lsb,
        enum_names_to_values(config.dataset_types),
        filepath=os.path.join("data", "val"),
        mode="val",
        down_sample_size=config.down_sample_size_test
    )

    print(train_dataset.dataset_sizes)
    print(test_dataset.dataset_sizes)
    print(val_dataset.dataset_sizes)