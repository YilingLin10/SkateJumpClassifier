from .layer.agcn import unit_gcn
from .utils.graph import Graph
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch import Tensor
import torch.nn.functional as F
from typing import Optional
import numpy as np
import math
from torchcrf import CRF

class PositionalEncoding(nn.Module):

    def __init__(self,
                 d_model, 
                 dropout=0.1, 
                 max_len=300):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)
        self.d_model = d_model
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        if d_model%2 != 0:
            pe[:, 1::2] = torch.cos(position * div_term)[:,0:-1]
        else:
            pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0).transpose(0, 1)
        self.register_buffer('pe', pe)

    def forward(self, x):
        # make embeddings relatively larger
        x = x * math.sqrt(self.d_model)
        x = x + self.pe[:x.size(0), :]
        return self.dropout(x)

class AGCN_Transformer(nn.Module):
    def __init__(self,
                 hidden_channel,
                 out_channel,
                 nhead, 
                 num_encoder_layers,
                 dim_feedforward,
                 dropout,
                 batch_first,
                 num_class,
                 use_crf,
                 layer_norm_eps = 1e-5,
                 activation = 'relu',
                 norm_first = False,
                 device=None, dtype=None):
        super(AGCN_Transformer, self).__init__()
        ## AGCN
        self.out_channel = out_channel
        self.hidden_channel = hidden_channel
        self.num_node = 17
        self.self_link = [(i, i) for i in range(self.num_node)]
        self.inward = [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 6), (5, 6),
                    (5, 7), (6, 8), (7, 9), (8, 10), (5, 11), (6, 12),
                    (11, 12), (11, 13), (12, 14), (13, 15), (14, 16)]
        self.outward = [(j, i) for (i, j) in self.inward]
        self.neighbor = self.inward + self.outward
        graph_args = {
            'num_node': self.num_node,
            'self_link': self.self_link,
            'inward': self.inward,
            'outward': self.outward,
            'neighbor': self.neighbor
        }
        self.graph = Graph(**graph_args)
        A = self.graph.A
        self.agcn1 = unit_gcn(2, self.hidden_channel , A)
        self.agcn2 = unit_gcn(self.hidden_channel, self.out_channel, A)
        self.data_bn = nn.BatchNorm1d(self.num_node * 2)
        ## Encoder
        factory_kwargs = {'device': device, 'dtype': dtype}
        self.d_model = self.out_channel
        self.pos_encoder = PositionalEncoding(d_model=self.d_model,
                                              dropout=dropout, 
                                              max_len=300)
        encoder_layer = nn.TransformerEncoderLayer(d_model=self.d_model,
                                                   nhead =nhead, 
                                                   dim_feedforward = dim_feedforward, 
                                                   dropout = dropout,
                                                   activation = activation, 
                                                   layer_norm_eps = layer_norm_eps, 
                                                   batch_first = batch_first, 
                                                   **factory_kwargs)
        encoder_norm = nn.LayerNorm(normalized_shape=self.d_model, 
                                    eps=layer_norm_eps, 
                                    **factory_kwargs)
        self.encoder = nn.TransformerEncoder(encoder_layer, num_encoder_layers, encoder_norm)
        self.out = nn.Linear(out_channel, num_class)
        self.use_crf = use_crf
        self.crf = CRF(num_tags=num_class, batch_first=batch_first)

    def _get_embeddings(self, src):
        ## TODO: batch normalization
        ## [batch_size, seq_len, 34] --> [batch_size, 34, seq_len]
        src = src.permute(0, 2, 1)
        src = self.data_bn(src)
        ## [batch_size, 34, seq_len] --> [batch_size, seq_len, 34]
        src = src.permute(0, 2, 1)

        ## TODO: AGCN embeddings
        N, T, _ = src.size()
        # input src = [batch_size, seq_len, 34] --> [batch_size, 2, seq_len, 17]
        src = src.view(N, T, self.num_node, 2).permute(0, 3, 1, 2)
        src = self.agcn1(src)
        src = self.agcn2(src)

        ## TODO:Global Average Pooling or Global Maximum pooling???
        ## output of agcn = [batch_size, out_channel, seq_len, 17] --> [batch_size, seq_len, out_channel]
        # src = src.mean(dim=3)
        src, _ = torch.max(src, 3)
        src = src.permute(0, 2, 1)
        return src

    def _get_encoder_feature(self, src, mask):
        src = self._get_embeddings(src)
        ### True: not attend, False: attend
        self.src_key_padding_mask = ~mask

        ## TODO: 2-layered Transformer encoder
        # [batch_size, seq_len, out_channel]
        src = self.pos_encoder(src)
        # output --> [batch_size, seq_len, out_channel]
        output = self.encoder(src, mask=None, src_key_padding_mask=self.src_key_padding_mask)
        if not self.use_crf:
            # output --> [batch_size * seq_len, out_channel]
            output = output.contiguous().view(N * T, -1)
        # output --> USE_CRF: [batch_size, seq_len, 4]  else: [batch_size * seq_len, 4]
        output = self.out(output)
        return output

    def forward(self, src, mask):
        output = self._get_encoder_feature(src, mask)
        if self.use_crf:
            ### type: List (for prediction)
            return self.crf.decode(output, mask)
        else:
            return F.log_softmax(output, dim=1)
    
    def loss_fn(self, src, target, mask):
        pred = self._get_encoder_feature(src, mask)
        return -self.crf.forward(pred, target, mask, reduction='mean')

if __name__ == '__main__':
    dataset = IceSkatingDataset(pkl_file='/home/lin10/projects/SkatingJumpClassifier/data/loop/alphapose/test.pkl',
                                tag_mapping_file='/home/lin10/projects/SkatingJumpClassifier/data/tag2idx.json',
                                use_crf=True,
                                add_noise=False,
                                subtract_feature=False)
    dataloader = DataLoader(dataset,batch_size=2,
                        shuffle=False, num_workers=1, collate_fn=dataset.collate_fn)

    model = AGCN_Transformer(
                    out_channel = 16,
                    nhead = 2, 
                    num_encoder_layers = 2,
                    dim_feedforward = 128,
                    dropout = 0.1,
                    batch_first = True,
                    num_class = 4,
                    use_crf = True).to('cuda')
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4, betas=(0.9, 0.999))

    for e in range(2):
        for i_batch, sample in enumerate(dataloader):
            keypoints, labels = sample['keypoints'].to('cuda'), sample['output'].to('cuda')
            mask = sample['mask'].to('cuda')
            output = model(keypoints, mask)
            print(output)
            print(model.state_dict())
            exit()