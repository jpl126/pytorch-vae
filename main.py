import os
import argparse
import scipy.special
import numpy as np
import torch
from torch import optim
from tensorboardX import SummaryWriter

from config import get_args
from data_loader import data_loaders
from vae import VAE

args = get_args()
if args.figs:
    from draw_figs import draw_figs
os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpu)
args.cuda = torch.cuda.is_available()
device = torch.device("cuda:0" if args.cuda else "cpu")
train_loader, test_loader = data_loaders(args)
torch.manual_seed(args.seed)
if args.cuda: torch.cuda.manual_seed_all(args.seed)
writer = SummaryWriter(args.out_dir)

def train(epoch):
    global train_step
    for batch_idx, (data, _) in enumerate(train_loader):
        optimizer.zero_grad()
        elbo = model(data, mean_n=args.mean_num, imp_n=args.importance_num)
        elbo = elbo.mean()
        loss = -elbo

        train_step += 1
        loss.backward()
        optimizer.step()
        if train_step % args.log_interval == 0:
            print('Train Epoch: {} ({:.0f}%)\tLoss: {:.6f}'.format(
                epoch, 100. * batch_idx / len(train_loader), loss.item()))
            writer.add_scalar('train/loss', loss.item(), train_step)
            writer.add_scalar('train/elbo', elbo.item(), train_step)

def test(epoch):
    loss_1_sum = loss_64_sum = ll_sum = 0
    for _, (data, _) in enumerate(test_loader):
        elbos = []
        for _ in range(5000):
            outs = model.forward_pass(data)
            elbo = model.elbo(true_x=data, z=outs['z'], x_dist=outs['x_dist'], z_dist=outs['z_dist'])
            elbos.append(elbo.cpu().data.numpy())
        loss_1 = np.mean(elbos, 0)
        loss_64 = scipy.special.logsumexp(elbos[:64], 0) - np.log(64)
        ll = scipy.special.logsumexp(elbos, 0) - np.log(len(elbos))
        loss_1_sum += loss_1.sum()
        loss_64_sum += loss_64.sum()
        ll_sum += ll.sum()
    print('==== Testing. LL: {:.4f} current lr: {} ====\n'.format(
        ll_sum / len(test_loader.dataset), optimizer.param_groups[0]['lr']))
    writer.add_scalar('test/Loss_1', loss_1_sum / len(test_loader.dataset), epoch)
    writer.add_scalar('test/Loss_64', loss_64_sum / len(test_loader.dataset), epoch)
    writer.add_scalar('test/LL', ll_sum / len(test_loader.dataset), epoch)

model = VAE(device, x_dim=args.x_dim, h_dim=args.h_dim, z_dim=args.z_dim,
            beta=args.beta, analytic_kl=args.analytic_kl).to(device)
optimizer = optim.Adam(model.parameters(), lr=args.learning_rate)

train_step = 0
learning_rates = [1e-3 * 10**-(j/7) for j in sum([[i] * 3**i for i in range(8)], [])]
for epoch in range(1, args.epochs + 1):
    optimizer.param_groups[0]['lr'] = learning_rates[epoch - 1]
    writer.add_scalar('learning_rate', optimizer.param_groups[0]['lr'], epoch)
    train(epoch)
    with torch.no_grad():
        if epoch % 10 == 1: test(epoch)
        if args.figs and epoch % 10 == 1: draw_figs(model, args, test_loader, epoch)

