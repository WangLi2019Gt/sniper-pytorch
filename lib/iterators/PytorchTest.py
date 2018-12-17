import torch.utils.data as data
import numpy as np
from multiprocessing import Pool
from data_utils.data_workers import im_worker
from multiprocessing.pool import ThreadPool
import math
import matplotlib.pyplot as plt

class PytorchTest(data.Dataset):
    def __init__(self, roidb, config, test_scale, batch_size=4, threads=8, nGPUs=1, pad_rois_to=400, crop_size=None,num_classes=None):
        self.crop_size = crop_size
        self.roidb = roidb
        self.batch_size = batch_size
        self.num_classes = num_classes if num_classes else roidb[0]['gt_overlaps'].shape[1]
        self.data_name = ['data', 'im_info', 'im_ids']
        self.label_name = None
        self.cur_i = 0
        self.label = []
        self.context_size = 320
        self.thread_pool = ThreadPool(threads)
        self.im_worker = im_worker(crop_size=None if not self.crop_size else self.crop_size[0], cfg=config, target_size=test_scale)
        self.test_scale = test_scale
        self.reset()

    def __len__(self):
        return len(self.inds)


    def __getitem__(self, item):
        num = item % self.batch_size
        if num == 0:
            self.get_chip_label_per_batch()

        return self.im_tensor_batch[num],self.im_info_batch[num],self.im_ids[num]


    def get_chip_label_per_batch(self):
        cur_from = self.cur_i
        cur_to = self.cur_i + self.batch_size
        self.cur_i = self.cur_i +self.batch_size

        roidb = [self.roidb[self.inds[i]] for i in range(cur_from, cur_to)]

        im_ids = np.array([self.inds[i] for i in range(cur_from, cur_to)])

        hor_flag = True if roidb[0]['width']>= roidb[0]['height'] else False
        max_size = [self.test_scale[0], self.test_scale[1]] if hor_flag else [self.test_scale[1], self.test_scale[0]]


        ims = []
        for i in range(self.batch_size):
            ims.append([roidb[i]['image'], max_size ,roidb[i]['flipped']])
        im_info = np.zeros((self.batch_size, 3))

        processed_list = self.thread_pool.map(self.im_worker.worker, ims)
        im_tensor = np.zeros((self.batch_size, 3, max_size[0], max_size[1]), dtype=np.float32)
        for i,p in enumerate(processed_list):
            im_info[i] = [p[2][0], p[2][1], p[1]]
            im_tensor[i] = p[0]
        self.im_tensor_batch = im_tensor
        self.im_info_batch = im_info
        self.im_ids = im_ids

    def reset(self):
        self.cur_i = 0
        widths = np.array([r['width'] for r in self.roidb])
        heights = np.array([r['height'] for r in self.roidb])
        horz_inds = np.where(widths >= heights)[0]
        vert_inds = np.where(widths<heights)[0]
        if horz_inds.shape[0]%self.batch_size>0:
            extra_horz = self.batch_size - (horz_inds.shape[0] % self.batch_size)
            horz_inds = np.hstack((horz_inds, horz_inds[0:extra_horz]))
        if vert_inds.shape[0]%self.batch_size>0:
            extra_vert = self.batch_size - (vert_inds.shape[0]%self.batch_size)
            vert_inds = np.hstack((vert_inds, vert_inds[0:extra_vert]))
        inds = np.hstack((horz_inds, vert_inds))
        extra = inds.shape[0] % self.batch_size
        assert extra==0,'The number of samples here should be divisible by batch size'
        self.inds = inds

