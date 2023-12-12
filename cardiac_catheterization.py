# -*- coding: utf-8 -*-
"""Cardiac_Catheterization.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1ntjn3Y9hybSd8FoclVr7s2ubIgSclg8K
"""

! pip install segmentation_models_pytorch

from torch.utils.data import Dataset, DataLoader, random_split
import torch, os, cv2, numpy as np
import matplotlib.pyplot as plt
from glob import glob
from torchvision import transforms as T
import albumentations as A
from PIL import Image
import gdown, cv2
import segmentation_models_pytorch as smp



# Commented out IPython magic to ensure Python compatibility.

# %load_ext autoreload
# %autoreload 2

def get_data(path, ds_name = "Cardiac_Catheterization"):


    if os.path.isdir(path): print(" Data is here"); pass

    # if pretrain file has not been dawnloaded yet

    else:
        os.makedirs(path, exist_ok=True)
        Url = "https://drive.google.com/file/d/1a_OZ6-BpMQi01NIkm4l54EzyMTzLNJGU/view?usp=sharing" if ds_name == "Cardiac_Catheterization" else None


        # get data ID

        data_id =  Url.split("/")[-2]

        # set prefix
        prefix = "https://drive.google.com/uc?/export=download&id="

        # Dawnload and checkpoint

        gdown.download(prefix+data_id, path, quiet=False)
        folder_names = glob(f"{path}/*")
#         folder_names = glob(f"{path}/*")
        print(folder_names)

        for folder_name in folder_names:

            os.system(f"unzip {folder_name} -d {path} ")
            os.remove(folder_name)

get_data(path="data_Cardiac", ds_name = "Cardiac_Catheterization")

def get_transformation(size):
    return [A.Compose([A.Resize(size, size),
                     A.HorizontalFlip(0.5),
                     A.GaussNoise(0.3),
                     A.VerticalFlip(0.5)], is_check_shapes=False),
            A.Compose([A.Resize(size, size)], is_check_shapes=False)]

tr_tr, ts_tr = get_transformation(size = 320)
tr_tr, ts_tr

class CustomDataset(Dataset):
    def __init__(self, root, transformations = None, im_files = [".png", ".jpg", ".jepg"]):
        super(). __init__()
        self.transformations =transformations
        self.tensorsize = T.Compose([T.ToTensor()])

#         self.im_path = sorted(glob(f"{root}/*/images/*"[{im for im in im_file}]))
#         self.gt_path = sorted(glob(f"{root}/*/images/*"[{im for im in im_file}]))

        self.im_path = sorted(glob(f"{root}/images/*[{im_file for im_file in im_files}]"))
        self.gt_path = sorted(glob(f"{root}/masks/*[{im_file for im_file in im_files}]"))
#         print(len(self.im_path))

    def __len__(self): return len(self.im_path)

    def __getitem__(self, idx):

#         try: cv2.cvtColor(cv2.imread(self.im_path[idx]), cv2.COLOR_BGR2RGB)
#         except: print(self.im_path[idx])

        im = cv2.cvtColor(cv2.imread(self.im_path[idx]), cv2.COLOR_BGR2RGB)
        gt = cv2.cvtColor(cv2.imread(self.gt_path[idx]), cv2.COLOR_BGR2GRAY)

#         print(idx)

        if self.transformations is not None:
            tr_ed = self.transformations(image = im , mask = gt)
            im = tr_ed['image']
            gt = tr_ed['mask']

        im = self.tensorsize(im)
        gt = torch.tensor(gt>128).long()


        return im, gt
data ="data_Cardiac/Cardiac_Catheterization/train"

ds = CustomDataset(root= data, transformations=ts_tr)
ds[5]
# print(ds[2][1].shape)

import numpy as np
def tn_2_np(t):
     return (t*255).detach().cpu().permute(1,2,0).numpy().astype(np.uint8) if len(t)==3 else (t*255).detach().cpu().numpy().astype(np.uint8)

for idx, data in enumerate(ds):
    if idx ==3: break

    im, gt =data
    display(Image.fromarray(tn_2_np(im)))
    display(Image.fromarray(tn_2_np(gt)))

def get_dls(root, transformations, bs,  split = [0.8, 0.1, 0.1]):

    ds = CustomDataset(root=root, transformations=transformations)
    tr_length = len(ds)

#     print(tr_length)
    tr_len = int(split[0]*tr_length)
    vl_len = int(split[1]*tr_length)
    test_len = tr_length - tr_len - vl_len

    tr_ds, val_ds, ts_ds = random_split(ds, [tr_len, vl_len, test_len ])

    print(f"Number of train dataset data         => {len(tr_ds)}")
    print(f"Number of validation dataset data    => {len(val_ds)}")
    print(f"Number of test dataset data          => {len(ts_ds)}")

    tr_dlr = DataLoader(tr_ds, batch_size=bs, shuffle=True, num_workers=0)
    val_dlr = DataLoader(tr_ds, batch_size=bs, shuffle=False, num_workers=0)
    ts_dlr = DataLoader(tr_ds, batch_size=1, shuffle=False, num_workers=0)

    return tr_dlr, val_dlr, ts_dlr

tr_dlr, val_dlr, ts_dlr  = get_dls(root="data_Cardiac/Cardiac_Catheterization/train", transformations= ts_tr, bs=16)

model = smp.Unet(encoder_name='resnet18', classes=2, encoder_depth = 5,
                encoder_weights = 'imagenet', activation=None, decoder_channels = [256, 128, 64, 32, 16])
model

loss_fn = torch.nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(params=model.parameters(), lr=0.001)
# device = "cude" if torch.cuda.is_available else 'cpu'
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

from tqdm import tqdm

class Metrics():
    def __init__(self, pred, gt, loss_fn, eps = 3e-4, num_class = 2):

        self.pred = torch.argmax(torch.nn.functional.softmax(pred, dim = 1), dim =1)

        self.gt = gt
        self.loss_fn = loss_fn
        self.pred_ = pred
        self.eps =eps
        self.num_class =num_class

    def to_contiguous(self, inp): return inp.contiguous().view(-1)

    #PA

    def PA(self):
        with torch.no_grad():

            match = torch.eq(self.pred, self.gt).int()

        return float(match.sum())/float(match.numel())

    #mIoU

    def mIoU(self):
        pred, gt = self.to_contiguous(self.pred), self.to_contiguous(self.gt)

        IoU_number_class = []

        for a in range(self.num_class):
            match_pred = pred == a
            match_gt =gt == a


            # print("\nmatch_pred size:", match_pred.size())
            # print("\nmatch_gt size:", match_gt.size())

            if match_gt.long().sum().item()==0: IoU_number_class.append(np.nan)
            else:
                intersection = torch.logical_and(match_pred, match_gt).sum().float().item()
                union = torch.logical_or(match_pred, match_gt).sum().float().item()



                iou = (intersection)/(union+self.eps)

                IoU_number_class.append(iou)

            return np.nanmean(IoU_number_class)

        # loss function
    def loss(self):


      return self.loss_fn(self.pred_, self.gt)



def train(model, tr_dlr, val_dlr, epochs, device, loss_fn, opt, save_prefix):

    tr_loss, tr_pa, tr_iou= [],[],[]
    val_loss, val_pa, val_iou = [],[],[]
    tr_len, val_len = len(tr_dlr), len(val_dlr)


    best_loss = np.inf
    decrease, not_improve, early_stop_threshold =1,0,6
    os.makedirs("save_file", exist_ok=True)

    model.to(device)

    print("Train is starting .......")

    for epoch in range(1, epochs+1):

        tr_loss_, tr_pa_, tr_iou_ = 0,0,0
        model.train()

        print(f"{epoch}- epoch training")
        for idx, batch in enumerate(tqdm(tr_dlr)):
            im, gt = batch
            im, gt = im.to(device), gt.to(device)


            pred = model(im)
            met = Metrics(pred, gt, loss_fn)


            loss_ =met.loss()

            tr_iou_+=met.mIoU()
            tr_pa_+=met.PA()
            tr_loss_+=loss_.item()

            opt.zero_grad()
            loss_.backward()
            opt.step()

        print(f"{epoch} - epoch validation starting")

        model.eval()
        val_loss_, val_pa_, val_iou_ = 0,0,0

        with torch.no_grad():
            for idx, batch in enumerate(tqdm(val_dlr)):

                im, gt = batch
                im, gt = im.to(device), gt.to(device)

                pred = model(im)

                met = Metrics(pred, gt, loss_fn)

                val_loss_ += met.loss().item()
                val_iou_ += met.mIoU()
                val_pa_ += met.PA()

        print(f"{epoch}- epoch train finished")

        tr_iou_/= tr_len
        tr_loss_/=tr_len
        tr_pa_/=tr_len

        val_iou_/=val_len
        val_loss_/=val_len
        val_pa_/= val_len

        print("\n ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print(f"{epoch}- epoch train result:\n")
        print(f"Train loss                 --> {tr_loss_:.3f}")
        print(f"Train PA                   --> {tr_pa_:.3f}")
        print(f"Train mIoU                 --> {tr_iou_:.3f}")

        print(f"Validation loss             --> {val_loss_:.3f}")
        print(f"Validation PA               --> {val_pa_:.3f}")
        print(f"Validation mIoU             --> {val_iou_:.3f}")


        tr_loss.append(tr_loss_)
        tr_pa.append(tr_pa_)
        tr_iou.append(tr_iou_)

        val_loss.append(val_loss_)
        val_pa.append(val_pa_)
        val_iou.append(val_iou_)


        if val_loss_ < best_loss:
            not_improve +=1
            decrease +=1
            best_loss = val_loss_

            if decrease % 2 ==0:
                print(f"The model with the lowest error is saved")
                torch.save(model, f"save_file/{save_prefix}_best_model.pt")


        if val_loss_ > best_loss:
            not_improve+=1

            best_loss = val_loss_

            print(f"Xatolik {not_improve} epoch davomida kamaygani yo'q!")

            if not_improve == early_stop_threshold:
                print(f"Xatolik {early_stop_threshold} epoch davomida kamaymagani uchun train jarayonini to'xtatamiz!")
                break
        print("---------------------------------------------------")

    return {"tr_loss": tr_loss, "tr_iou": tr_iou, 'tr_pa': tr_pa,
           "val_loss": val_loss, "val_iou": val_iou, 'val_pa': val_pa}

results = train(model = model, tr_dlr=tr_dlr, val_dlr=val_dlr, epochs=10,
               device=device, loss_fn=loss_fn, opt=optimizer, save_prefix="save_file")

results

import matplotlib.pyplot as plt

class Plot():
    def __init__(self, res):


        plt.figure(figsize =(10,5))
        plt.plot(res['tr_iou'], label = 'Train_IoU')
        plt.plot(res['val_iou'], label = 'Valid_IoU')
        plt.title("Mean intersection Over Union Learning Curve")
        plt.xlabel('Epochs')
        plt.xticks(np.arange(len(res['val_iou'])), [i for i in range(1, len(res['val_iou']) + 1)])
        plt.ylabel('MIoU Score')
        plt.ylim(0, 1)
        plt.legend()
        plt.show()

        plt.figure(figsize = (10, 5))
        plt.plot(res['tr_pa'], label = "Train PA")
        plt.plot(res['val_pa'], label = "Validetion PA")
        plt.title("Pexel Accuracy Learning Curve")
        plt.xlabel('Epochs')
        plt.xticks(np.arange(len(res['val_pa'])), [i for i in range(1, len(res['val_pa']) + 1)])
        plt.ylabel("PA")
        plt.ylim(0, 1)
        plt.legend()
        plt.show()

        plt.figure(figsize = (10, 5))
        plt.plot(res['tr_loss'], label = "Train Loss")
        plt.plot(res['val_loss'], label = "Validation Loss")
        plt.title("Validation Loss Learning Curve")
        plt.xlabel('Epochs')
        plt.xticks(np.arange(len(res['val_loss'])), [i for i in range(1, len(res['val_loss']) + 1)])


        plt.ylabel("Loss value")
        plt.ylim(0, 1)
        plt.legend()
        plt.show()
Plot(results)

def inference(dl, model, device):
  count =1
  for idx, batch in enumerate(dl):
    if idx==2: break
    im, gt =batch

    pred = model(im.to(device))

    plt.figure(figsize= (10, 5))
    plt.subplot(2, 3, count)
    plt.imshow(tn_2_np(im.squeeze(0)))
    plt.axis("off")
    plt.title("Orginal")

    count+=1

    plt.subplot(2,3, count)
    plt.imshow(gt.squeeze(0), cmap = "gray")
    plt.title("Ground Truth")
    plt.axis("off")
    count+=1

    plt.subplot(2, 3, count)
    plt.imshow(tn_2_np((pred >0.5).squeeze(0))[1], cmap="gray")
    plt.title("Predicted Mask")
    plt.axis("off")
    plt.show()
    count += 1



model = torch.load("save_file/save_file_best_model.pt")
inference( ts_dlr, model = model, device = device)

