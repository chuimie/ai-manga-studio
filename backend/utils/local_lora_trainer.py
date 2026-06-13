"""
本地LoRA训练引擎（CPU/AMD AI 9 H365兼容）
基于 diffusers + peft，在 CPU 上训练 LoRA 权重
"""

import os
import re
import time
import torch
import numpy as np
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from diffusers import StableDiffusionPipeline, DDIMScheduler
from peft import LoraConfig, get_peft_model, get_peft_model_state_dict
from safetensors.torch import save_file as safetensors_save
from typing import Optional


# ─────────────────────────────────────────────
# 数据集：读取训练集目录中的图片+字幕后返回
# ─────────────────────────────────────────────

class LoRATrainingDataset(Dataset):
    """从标准训练集目录加载图文对"""

    def __init__(self, dataset_dir: str, resolution: int = 512):
        self.samples = []
        self.resolution = resolution

        # 读取所有图片文件
        img_exts = {'.png', '.jpg', '.jpeg', '.webp'}
        for fname in sorted(os.listdir(dataset_dir)):
            ext = os.path.splitext(fname)[1].lower()
            if ext in img_exts:
                img_path = os.path.join(dataset_dir, fname)
                # 对应的 caption 文件（同名 .txt）
                cap_path = os.path.join(
                    dataset_dir,
                    fname.rsplit('.', 1)[0] + '.txt'
                )
                caption = ""
                if os.path.exists(cap_path):
                    with open(cap_path, 'r', encoding='utf-8') as f:
                        caption = f.read().strip()
                self.samples.append((img_path, caption))

        if not self.samples:
            raise ValueError(f"训练集目录为空: {dataset_dir}")

        print(f"[本地LoRA] 加载训练集: {len(self.samples)} 张图片")
        print(f"[本地LoRA] 触发词: {self.samples[0][1].split(',')[0] if self.samples[0][1] else '无'}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, caption = self.samples[idx]

        # 加载并预处理图片
        image = Image.open(img_path).convert('RGB')
        image = image.resize((self.resolution, self.resolution), Image.LANCZOS)
        img_array = np.array(image).astype(np.float32) / 127.5 - 1.0
        pixel_values = torch.from_numpy(img_array).permute(2, 0, 1)

        return {
            "pixel_values": pixel_values,
            "caption":      caption
        }


# ─────────────────────────────────────────────
# 主训练函数
# ─────────────────────────────────────────────

def train_lora_local(
    dataset_dir: str,
    output_path: str,
    trigger_word: str,
    base_model: str = "runwayml/stable-diffusion-v1-5",
    resolution: int = 512,
    train_steps: int = 500,
    learning_rate: float = 1e-4,
    network_dim: int = 16,
    network_alpha: int = 8,
    batch_size: int = 1,
    save_every: Optional[int] = None,
) -> str:
    """
    在 CPU 上训练 LoRA 权重

    参数:
        dataset_dir:  训练集目录（图片 + .txt字幕）
        output_path:  输出 .safetensors 路径
        trigger_word: LoRA触发词
        base_model:   HuggingFace模型ID 或 本地路径
        resolution:   训练分辨率（CPU建议512，越小越快）
        train_steps:  训练步数（CPU建议500-1000）
        learning_rate:学习率
        network_dim:  LoRA秩（越小越快，16-32）
        network_alpha:LoRA alpha（通常=dim/2）
        batch_size:   批大小（CPU只能=1）
        save_every:   每N步保存一次中间结果（None=不保存）

    返回:
        输出权重文件路径
    """
    device = torch.device("cpu")
    dtype  = torch.float32

    # 提示CPU训练耗时
    estimated_min = (train_steps * 3) // 60  # 粗略估计每步~3秒
    print(f"[本地LoRA] ⚠️  CPU训练预计约 {estimated_min} 分钟")
    print(f"[本地LoRA]    - 模型: {base_model}")
    print(f"[本地LoRA]    - 步数: {train_steps}")
    print(f"[本地LoRA]    - 分辨率: {resolution}x{resolution}")
    print(f"[本地LoRA]    - LoRA dim: {network_dim}, alpha: {network_alpha}")
    print()

    # ── 1. 加载基础模型 ─────────────────────
    print("[本地LoRA] 正在加载基础模型（首次会下载，约1.7GB）...")
    t0 = time.time()

    pipe = StableDiffusionPipeline.from_pretrained(
        base_model,
        torch_dtype=dtype,
        safety_checker=None,        # 禁用安全检查（加快速度）
        requires_safety_checker=False,
    )
    pipe = pipe.to(device)

    # 提取组件
    tokenizer    = pipe.tokenizer
    text_encoder = pipe.text_encoder
    vae          = pipe.vae
    unet         = pipe.unet
    scheduler    = DDIMScheduler.from_config(pipe.scheduler.config)

    # 冻结不需要训练的部分
    vae.requires_grad_(False)
    text_encoder.requires_grad_(False)

    print(f"[本地LoRA] 模型加载完成 ({time.time()-t0:.1f}秒)")

    # ── 2. 注入 LoRA ────────────────────────
    print("[本地LoRA] 注入 LoRA 适配器...")

    lora_config = LoraConfig(
        r                = network_dim,
        lora_alpha       = network_alpha,
        target_modules   = ["to_q", "to_k", "to_v", "to_out.0"],
        lora_dropout     = 0.0,
        bias             = "none",
    )
    unet = get_peft_model(unet, lora_config)
    unet.train()

    # 只训练 LoRA 参数
    params_to_train = [p for p in unet.parameters() if p.requires_grad]
    total_params    = sum(p.numel() for p in params_to_train)
    print(f"[本地LoRA] 可训练参数: {total_params:,} ({total_params/1e6:.2f}M)")

    # ── 3. 准备数据 ─────────────────────────
    dataset = LoRATrainingDataset(dataset_dir, resolution=resolution)
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,          # CPU 训练不用多进程加载
    )

    # ── 4. 优化器 ───────────────────────────
    optimizer = torch.optim.AdamW(params_to_train, lr=learning_rate)

    # ── 5. 训练循环 ─────────────────────────
    print(f"\n[本地LoRA] 开始训练 ({train_steps} 步)...")
    print(f"[本地LoRA] 按 Ctrl+C 可中断并保存当前进度")

    global_step = 0
    loss_sum    = 0.0
    log_interval = max(1, train_steps // 20)  # 约每5%报告一次
    t_start     = time.time()

    try:
        while global_step < train_steps:
            for batch in dataloader:
                if global_step >= train_steps:
                    break

                # 获取像素值（[-1, 1]）
                pixel_values = batch["pixel_values"].to(dtype=dtype)
                captions     = batch["caption"]

                # ── VAE 编码到潜空间 ──
                latents = vae.encode(pixel_values).latent_dist.sample()
                latents = latents * vae.config.scaling_factor

                # ── 随机噪声 ──
                noise = torch.randn_like(latents)
                timesteps = torch.randint(
                    0, scheduler.config.num_train_timesteps,
                    (latents.shape[0],), dtype=torch.long
                )
                noisy_latents = scheduler.add_noise(latents, noise, timesteps)

                # ── 文本编码 ──
                tokens = tokenizer(
                    captions,
                    padding="max_length",
                    max_length=tokenizer.model_max_length,
                    truncation=True,
                    return_tensors="pt",
                ).input_ids.to(device)
                encoder_hidden_states = text_encoder(tokens)[0]

                # ── UNet 预测噪声 ──
                noise_pred = unet(
                    noisy_latents, timesteps,
                    encoder_hidden_states
                ).sample

                # ── 损失 ──
                loss = torch.nn.functional.mse_loss(
                    noise_pred, noise, reduction="mean"
                )

                # 反向传播
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                loss_sum += loss.item()
                global_step += 1

                # 日志
                if global_step % log_interval == 0 or global_step == 1:
                    avg_loss = loss_sum / min(global_step, log_interval)
                    elapsed  = time.time() - t_start
                    remaining = (elapsed / global_step) * (train_steps - global_step)
                    print(
                        f"  Step {global_step:>5d}/{train_steps}  "
                        f"Loss: {avg_loss:.4f}  "
                        f"已过: {elapsed:.0f}s  "
                        f"预计剩余: {remaining:.0f}s"
                    )
                    loss_sum = 0.0

                # 中间保存
                if save_every and global_step % save_every == 0:
                    _save_lora_weights(unet, output_path.replace(
                        ".safetensors", f"_step{global_step}.safetensors"
                    ))

    except KeyboardInterrupt:
        print(f"\n[本地LoRA] ⏸️  训练被中断，保存当前进度...")
    finally:
        # ── 权重保存（成功或中断都保存当前权重） ──
        t_train = time.time() - t_start
        print(f"\n[本地LoRA] 总耗时: {t_train:.0f}秒 ({t_train/60:.1f}分钟)")

        if global_step > 0:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            _save_lora_weights(unet, output_path)
            print(f"[本地LoRA] ✅ 权重已保存: {output_path}")
        else:
            print("[本地LoRA] ⚠️  未进行任何训练步，无权重保存")

        # ── 资源释放（始终执行） ──
        _cleanup_training(
            pipe=pipe,
            unet=unet,
            vae=vae,
            text_encoder=text_encoder,
            tokenizer=tokenizer,
            scheduler=scheduler,
            optimizer=optimizer,
            dataset=dataset,
            dataloader=dataloader,
        )

    return output_path


def _cleanup_training(
    pipe,
    unet,
    vae,
    text_encoder,
    tokenizer,
    scheduler,
    optimizer,
    dataset,
    dataloader,
):
    """训练完成后释放所有模型资源，防止内存泄漏"""
    import gc

    print("[本地LoRA] 清理训练资源...")

    # 记录清理前内存（仅限psutil可用时）
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem_before = proc.memory_info().rss / (1024 ** 3)
    except ImportError:
        mem_before = None

    # 逐个释放组件
    del pipe
    del unet
    del vae
    del text_encoder
    del tokenizer
    del scheduler
    del optimizer
    del dataset
    del dataloader

    # 强制垃圾回收
    gc.collect()

    # 如果可用，报告释放量
    try:
        import psutil
        mem_after = proc.memory_info().rss / (1024 ** 3)
        freed = mem_before - mem_after
        print(f"[本地LoRA] 内存释放: {freed:.1f}GB ({mem_before:.1f}GB → {mem_after:.1f}GB)")
    except ImportError:
        print("[本地LoRA] 内存清理完成（安装 psutil 可查看详细释放量）")


# ─────────────────────────────────────────────
# 保存 LoRA 权重（与 diffusers 兼容格式）
# ─────────────────────────────────────────────

def _save_lora_weights(unet, output_path: str):
    """将 UNet 中的 LoRA 权重提取并保存为 .safetensors"""
    state_dict = get_peft_model_state_dict(unet)

    # 转换键名，兼容 diffusers 加载格式
    diffusers_state_dict = {}
    for key, value in state_dict.items():
        # peft格式: base_model.model.down_blocks.0.attentions.0.transformer_blocks.0.attn1.to_q.lora_A.weight
        # diffusers格式: down_blocks.0.attentions.0.transformer_blocks.0.attn1.to_q.lora.down.weight
        new_key = key.replace("base_model.model.", "")
        new_key = re.sub(
            r'\.(lora_A|lora_B)\.',
            lambda m: '.lora.down.' if m.group(1) == 'lora_A' else '.lora.up.',
            new_key
        )
        diffusers_state_dict[new_key] = value

    safetensors_save(diffusers_state_dict, output_path)


# ─────────────────────────────────────────────
# 本地训练配置（覆盖默认的云端配置）
# ─────────────────────────────────────────────

LOCAL_TRAIN_CONFIG = {
    "base_model":    os.getenv("LOCAL_BASE_MODEL", "runwayml/stable-diffusion-v1-5"),
    "resolution":    384,        # CPU建议低分辨率
    "train_steps":   500,        # CPU步数减半
    "learning_rate": 1e-4,
    "network_dim":   16,         # CPU用更小的rank
    "network_alpha": 8,
    "batch_size":    1,
}