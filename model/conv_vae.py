import torch
from torch import nn
from torch.distributions.normal import Normal
from .vae_base import VAE


class Flatten(nn.Module):
    # FIXME: integrate so that plot etc works.
    def forward(self, input):
        return input.view(input.size(0), 16 * 8 * 8).contiguous()


class UnFlatten(nn.Module):
    def forward(self, input):
        return input.view(input.size(0), 16, 8, 8).contiguous()


class ConvVAE(VAE):
    def __init__(self, device, x_dim, h_dim, z_dim, beta, analytic_kl, mean_img):
        VAE.__init__(self, device, x_dim, h_dim, z_dim, beta, analytic_kl, mean_img)
        self.proc_data = lambda x: x.to(device)
        self.encoder = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=1, padding=1), nn.ReLU(),
            nn.Conv2d(32, 32, kernel_size=3, stride=2, padding=1), nn.ReLU(),
            nn.Conv2d(32, 32, kernel_size=3, stride=1, padding=1), nn.ReLU(),
            nn.Conv2d(32, 16, kernel_size=3, stride=2, padding=1), nn.ReLU(),
            Flatten())
        self.enc_mu = nn.Linear(16 * 8 * 8, z_dim)
        self.enc_sig = nn.Linear(16 * 8 * 8, z_dim)
        self.decoder = nn.Sequential(
            nn.Linear(z_dim, 16 * 8 * 8), nn.ReLU(),
            UnFlatten(),
            nn.ConvTranspose2d(16, 32, kernel_size=3, stride=2, padding=1, output_padding=1), nn.ReLU(),
            nn.ConvTranspose2d(32, 32, kernel_size=3, stride=1, padding=1), nn.ReLU(),
            nn.ConvTranspose2d(32, 32, kernel_size=3, stride=2, padding=1, output_padding=1), nn.ReLU(),
            nn.ConvTranspose2d(32, 6, kernel_size=3, stride=1, padding=1))

        self.apply(self.init)
        self.mean_img = torch.nn.Parameter(torch.Tensor(mean_img)).to(device).permute(2, 0, 1).detach()

    def decode(self, z):
        mean_n, imp_n, bs = z.size(0), z.size(1), z.size(2)
        z = z.view([mean_n * imp_n * bs, -1]).contiguous()
        x = self.decoder(z)
        x = x.view([mean_n, imp_n, bs, 6, 32, 32]).contiguous()
        x_mean, x_std = x[:, :, :, :3, :, :].contiguous(), nn.functional.softplus(x[:, :, :, 3:, :, :]).contiguous()
        return Normal(x_mean, x_std)
