# -*- coding: utf-8 -*-
#
# Developed by Haozhe Xie <cshzxie@gmail.com>

import json
import logging
import os
import random
import sys
from enum import Enum, unique

import numpy as np
import scipy.io
import scipy.ndimage
import torch.utils.data.dataset
from PIL import Image

import utils.binvox_rw


@unique
class DatasetType(Enum):
    TRAIN = 0
    TEST = 1
    VAL = 2


# //////////////////////////////// = End of DatasetType Class Definition = ///////////////////////////////// #


class ShapeNetDataset(torch.utils.data.dataset.Dataset):
    """ShapeNetDataset class used for PyTorch DataLoader"""

    def __init__(self, dataset_type, file_list, n_views_rendering, transforms=None):
        self.dataset_type = dataset_type
        self.file_list = file_list
        self.transforms = transforms
        self.n_views_rendering = n_views_rendering

    def __len__(self):
        return len(self.file_list)

    def __getitem__(self, idx):
        taxonomy_name, sample_name, rendering_images, volume = self.get_datum(idx)

        if self.transforms:
            rendering_images = self.transforms(rendering_images)

        return taxonomy_name, sample_name, rendering_images, volume

    def set_n_views_rendering(self, n_views_rendering):
        self.n_views_rendering = n_views_rendering

    def get_datum(self, idx):
        taxonomy_name = self.file_list[idx]['taxonomy_name']
        sample_name = self.file_list[idx]['sample_name']
        rendering_image_paths = self.file_list[idx]['rendering_images']
        volume_path = self.file_list[idx]['volume']

        # Get data of rendering images
        if self.dataset_type == DatasetType.TRAIN:
            selected_rendering_image_paths = [
                rendering_image_paths[i]
                for i in random.sample(range(len(rendering_image_paths)), self.n_views_rendering)
            ]
        else:
            selected_rendering_image_paths = [rendering_image_paths[i] for i in range(self.n_views_rendering)]

        rendering_images = []
        for image_path in selected_rendering_image_paths:
            rendering_image = np.asarray(Image.open(image_path)).astype(np.float32) / 255.
            if len(rendering_image.shape) < 3:
                logging.error('It seems that there is something wrong with the image file %s' % (image_path))
                sys.exit(2)

            rendering_images.append(rendering_image)

        # Get data of volume
        _, suffix = os.path.splitext(volume_path)

        if suffix == '.mat':
            volume = scipy.io.loadmat(volume_path)
            volume = volume['Volume'].astype(np.float32)
        elif suffix == '.binvox':
            with open(volume_path, 'rb') as f:
                volume = utils.binvox_rw.read_as_3d_array(f)
                volume = volume.data.astype(np.float32)

        return taxonomy_name, sample_name, np.asarray(rendering_images), volume


# //////////////////////////////// = End of ShapeNetDataset Class Definition = ///////////////////////////////// #


class ShapeNetDataLoader:
    def __init__(self, cfg):
        self.dataset_taxonomy = None
        self.rendering_image_path_template = cfg.DATASETS.SHAPENET.RENDERING_PATH
        self.volume_path_template = cfg.DATASETS.SHAPENET.VOXEL_PATH

        # Load all taxonomies of the dataset
        with open(cfg.DATASETS.SHAPENET.TAXONOMY_FILE_PATH, encoding='utf-8') as file:
            self.dataset_taxonomy = json.loads(file.read())

    def get_dataset(self, dataset_type, n_views_rendering, transforms=None, ratio=1):
        files = []

        # Load data for each category
        for taxonomy in self.dataset_taxonomy:
            taxonomy_folder_name = taxonomy['taxonomy_id']
            logging.info('Collecting files of Taxonomy[ID=%s, Name=%s]' %
                         (taxonomy['taxonomy_id'], taxonomy['taxonomy_name']))
            samples = []
            if dataset_type.value == DatasetType.TRAIN.value:
                samples = taxonomy['train']
            elif dataset_type.value == DatasetType.TEST.value:
                samples = taxonomy['test']
            elif dataset_type.value == DatasetType.VAL.value:
                samples = taxonomy['val']

            files_of_taxonomy = self.get_files_of_taxonomy(taxonomy_folder_name, samples)
            number_of_files = len(files_of_taxonomy)
            number_of_files_to_be_selected = round(number_of_files / ratio)

            files.extend(files_of_taxonomy[:number_of_files_to_be_selected])

        logging.info('Complete collecting files of the dataset. Total files: %d.' % (len(files)))
        return ShapeNetDataset(dataset_type, files, n_views_rendering, transforms)

    def get_files_of_taxonomy(self, taxonomy_folder_name, samples):
        files_of_taxonomy = []

        for sample_idx, sample_name in enumerate(samples):
            # Get file path of volumes
            volume_file_path = self.volume_path_template % (taxonomy_folder_name, sample_name)
            if not os.path.exists(volume_file_path):
                logging.warn('Ignore sample %s/%s since volume file not exists.' % (taxonomy_folder_name, sample_name))
                continue

            # Get file list of rendering images
            img_file_path = self.rendering_image_path_template % (taxonomy_folder_name, sample_name, 0)
            img_folder = os.path.dirname(img_file_path)
            total_views = len(os.listdir(img_folder))
            rendering_image_indexes = range(total_views)
            rendering_images_file_path = []
            for image_idx in rendering_image_indexes:
                img_file_path = self.rendering_image_path_template % (taxonomy_folder_name, sample_name, image_idx)
                if not os.path.exists(img_file_path):
                    continue

                rendering_images_file_path.append(img_file_path)

            if len(rendering_images_file_path) == 0:
                logging.warn('Ignore sample %s/%s since image files not exists.' % (taxonomy_folder_name, sample_name))
                continue

            # Append to the list of rendering images
            files_of_taxonomy.append({
                'taxonomy_name': taxonomy_folder_name,
                'sample_name': sample_name,
                'rendering_images': rendering_images_file_path,
                'volume': volume_file_path,
            })

        return files_of_taxonomy


# /////////////////////////////// = End of ShapeNetDataLoader Class Definition = /////////////////////////////// #


class MVSDataset(torch.utils.data.dataset.Dataset):
    """MVSDataset class used for PyTorch DataLoader"""

    def __init__(self, dataset_type, file_list, n_views_rendering, transforms=None, target_size=(224, 224)):
        self.dataset_type = dataset_type
        self.file_list = file_list
        self.transforms = transforms
        self.n_views_rendering = n_views_rendering
        self.target_size = target_size

    def __len__(self):
        return len(self.file_list)

    def __getitem__(self, idx):
        taxonomy_name, sample_name, rendering_images, volume = self.get_datum(idx)

        if self.transforms:
            rendering_images = self.transforms(rendering_images)

        return taxonomy_name, sample_name, rendering_images, volume

    def set_n_views_rendering(self, n_views_rendering):
        self.n_views_rendering = n_views_rendering

    def get_datum(self, idx):
        taxonomy_name = self.file_list[idx]['taxonomy_name']
        sample_name = self.file_list[idx]['sample_name']
        rendering_image_paths = self.file_list[idx]['rendering_images']
        volume_path = self.file_list[idx]['volume']

        # Get data of rendering images
        if self.dataset_type == DatasetType.TRAIN:
            selected_rendering_image_paths = [
                rendering_image_paths[i]
                for i in random.sample(range(len(rendering_image_paths)), self.n_views_rendering)
            ]
        else:
            selected_rendering_image_paths = [rendering_image_paths[i] for i in range(self.n_views_rendering)]

        rendering_images = []
        for image_path in selected_rendering_image_paths:
            pil_image = Image.open(image_path)
            image_resized = pil_image.resize(self.target_size)
            rendering_image = np.asarray(image_resized).astype(np.float32) / 255.

            if len(rendering_image.shape) < 3:
                logging.error('It seems that there is something wrong with the image file %s' % (image_path))
                sys.exit(2)

            rendering_images.append(rendering_image)

        # Get data of volume
        _, suffix = os.path.splitext(volume_path)

        if suffix == '.mat':
            volume = scipy.io.loadmat(volume_path)
            volume = volume['Volume'].astype(np.float32)
        elif suffix == '.binvox':
            with open(volume_path, 'rb') as f:
                volume = utils.binvox_rw.read_as_3d_array(f)
                volume = volume.data.astype(np.float32)

        return taxonomy_name, sample_name, np.asarray(rendering_images), volume


# //////////////////////////////// = End of MVSDataset Class Definition = ///////////////////////////////// #


class MVSDataLoader:
    def __init__(self, cfg):
        self.dataset_taxonomy = None
        self.rendering_image_path_template = cfg.DATASETS.MVS.RENDERING_PATH
        self.volume_path_template = cfg.DATASETS.MVS.VOXEL_PATH
        self.target_size = (cfg.CONST.IMG_W, cfg.CONST.IMG_H)

        # Load all taxonomies of the dataset
        with open(cfg.DATASETS.MVS.TAXONOMY_FILE_PATH, encoding='utf-8') as file:
            self.dataset_taxonomy = json.loads(file.read())

    def get_dataset(self, dataset_type, n_views_rendering, transforms=None):
        files = []

        # Load data for each category
        for taxonomy in self.dataset_taxonomy:
            taxonomy_folder_name = taxonomy['taxonomy_id']
            logging.info('Collecting files of Taxonomy[ID=%s, Name=%s]' %
                         (taxonomy['taxonomy_id'], taxonomy['taxonomy_name']))
            samples = []
            if dataset_type.value == DatasetType.TRAIN.value:
                samples = taxonomy['train']
            elif dataset_type.value == DatasetType.TEST.value:
                samples = taxonomy['test']
            elif dataset_type.value == DatasetType.VAL.value:
                samples = taxonomy['val']

            files.extend(self.get_files_of_taxonomy(taxonomy_folder_name, samples))

        logging.info('Complete collecting files of the dataset. Total files: %d.' % (len(files)))
        return MVSDataset(dataset_type, files, n_views_rendering, transforms, self.target_size)

    def get_files_of_taxonomy(self, taxonomy_folder_name, samples):
        files_of_taxonomy = []

        for sample_idx, sample_name in enumerate(samples):
            # Get file path of volumes
            sample_number = int(sample_name[4:])
            sample_str = f"{int(sample_number):03d}"

            volume_file_path = self.volume_path_template % (sample_str)
            if not os.path.exists(volume_file_path):
                logging.warn('Ignore sample %s/%s since volume file not exists.' % (taxonomy_folder_name, sample_name))
                continue

            # Get file list of rendering images
            img_file_path = self.rendering_image_path_template % (sample_number, 1)
            img_folder = os.path.dirname(img_file_path)
            total_views = len(os.listdir(img_folder))
            rendering_image_indexes = range(total_views)
            rendering_images_file_path = []
            for image_idx in rendering_image_indexes:
                img_file_path = self.rendering_image_path_template % (sample_number, image_idx + 1)
                if not os.path.exists(img_file_path):
                    continue

                rendering_images_file_path.append(img_file_path)

            if len(rendering_images_file_path) == 0:
                logging.warn('Ignore sample %s/%s since image files not exists.' % (taxonomy_folder_name, sample_name))
                continue

            # Append to the list of rendering images
            files_of_taxonomy.append({
                'taxonomy_name': taxonomy_folder_name,
                'sample_name': sample_name,
                'rendering_images': rendering_images_file_path,
                'volume': volume_file_path,
            })

        return files_of_taxonomy


# /////////////////////////////// = End of MVSDataLoader Class Definition = /////////////////////////////// #


class MixedDataset(torch.utils.data.dataset.Dataset):
    """MVSDataset class used for PyTorch DataLoader"""

    def __init__(self, shapenet_dataset, mvs_dataset):
        self.shapenet_dataset = shapenet_dataset
        self.mvs_dataset = mvs_dataset

    def __len__(self):
        return len(self.shapenet_dataset.file_list) + len(self.mvs_dataset.file_list)

    def __getitem__(self, idx):
        if idx < len(self.mvs_dataset.file_list):
            taxonomy_name, sample_name, rendering_images, volume = self.mvs_dataset.get_datum(idx)

            if self.mvs_dataset.transforms:
                rendering_images = self.mvs_dataset.transforms(rendering_images)

            return taxonomy_name, sample_name, rendering_images, volume
        else:
            idx = idx - len(self.mvs_dataset.file_list)
            taxonomy_name, sample_name, rendering_images, volume = self.shapenet_dataset.get_datum(idx)

            if self.shapenet_dataset.transforms:
                rendering_images = self.shapenet_dataset.transforms(rendering_images)

            return taxonomy_name, sample_name, rendering_images, volume

    def set_n_views_rendering(self, n_views_rendering):
        self.shapenet_dataset.set_n_views_rendering(n_views_rendering)
        self.mvs_dataset.set_n_views_rendering(n_views_rendering)


# //////////////////////////////// = End of MixedDataset Class Definition = ///////////////////////////////// #


class MixedDataLoader:
    def __init__(self, cfg):
        self.shapenet_data_loader = ShapeNetDataLoader(cfg)
        self.mvs_data_loader = MVSDataLoader(cfg)
        self.shapenet_ratio = cfg.CONST.SHAPENET_RATIO

    def get_dataset(self, dataset_type, n_views_rendering, transforms=None):
        return MixedDataset(self.shapenet_data_loader.get_dataset(dataset_type, n_views_rendering, transforms,
                                                                  ratio=self.shapenet_ratio),
                            self.mvs_data_loader.get_dataset(dataset_type, n_views_rendering, transforms))


# /////////////////////////////// = End of MixedDataLoader Class Definition = /////////////////////////////// #


DATASET_LOADER_MAPPING = {
    'ShapeNet': ShapeNetDataLoader,
    'MVS': MVSDataLoader,
    'Mixed': MixedDataLoader
}
