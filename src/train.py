"""
Production Training Script for Glaucoma Detection
Robust, optimized, error-handled training pipeline
"""
import os
import sys
import yaml
import torch
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm
import argparse
from datetime import datetime
import numpy as np
import warnings
warnings.filterwarnings('ignore')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from model import create_model, optimize_for_cpu, export_to_torchscript
from dataset import create_dataloaders
from utils import (
    get_loss_function, MetricsCalculator, EarlyStopping,
    save_checkpoint, plot_confusion_matrix, plot_roc_curve,
    log_metrics
)


def train_one_epoch(model, dataloader, criterion, optimizer, device, epoch, gradient_accumulation_steps=1):
    """Train for one epoch with gradient accumulation"""
    model.train()
    running_loss = 0.0
    metrics_calc = MetricsCalculator()
    
    optimizer.zero_grad()
    
    pbar = tqdm(dataloader, desc=f'Epoch {epoch} [Train]', ncols=100)
    for batch_idx, (images, labels) in enumerate(pbar):
        try:
            images = images.to(device, memory_format=torch.channels_last)
            labels = labels.to(device).unsqueeze(1)
            
            # Forward pass
            logits = model(images)
            loss = criterion(logits, labels)
            loss = loss / gradient_accumulation_steps
            
            # Backward pass
            loss.backward()
            
            # Gradient accumulation
            if (batch_idx + 1) % gradient_accumulation_steps == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                optimizer.zero_grad()
            
            # Metrics
            probs = torch.sigmoid(logits)
            metrics_calc.update(probs, labels)
            running_loss += loss.item() * gradient_accumulation_steps
            
            pbar.set_postfix({
                'loss': f'{loss.item() * gradient_accumulation_steps:.4f}',
                'lr': f'{optimizer.param_groups[0]["lr"]:.6f}'
            })
            
        except Exception as e:
            print(f"\n⚠️ Error in batch {batch_idx}: {str(e)}")
            continue
    
    avg_loss = running_loss / len(dataloader)
    metrics = metrics_calc.compute()
    
    return avg_loss, metrics


@torch.no_grad()
def validate(model, dataloader, criterion, device, epoch):
    """Validate model with error handling"""
    model.eval()
    running_loss = 0.0
    metrics_calc = MetricsCalculator()
    
    pbar = tqdm(dataloader, desc=f'Epoch {epoch} [Val]', ncols=100)
    for batch_idx, (images, labels) in enumerate(pbar):
        try:
            images = images.to(device, memory_format=torch.channels_last)
            labels = labels.to(device).unsqueeze(1)
            
            logits = model(images)
            loss = criterion(logits, labels)
            
            probs = torch.sigmoid(logits)
            metrics_calc.update(probs, labels)
            running_loss += loss.item()
            
            pbar.set_postfix({'loss': f'{loss.item():.4f}'})
            
        except Exception as e:
            print(f"\n⚠️ Error in validation batch {batch_idx}: {str(e)}")
            continue
    
    avg_loss = running_loss / max(len(dataloader), 1)
    metrics = metrics_calc.compute()
    
    return avg_loss, metrics, metrics_calc


def train(config, resume_from=None):
    """Production-grade training function"""
    
    device = torch.device('cpu')
    os.makedirs(config['checkpoint']['save_dir'], exist_ok=True)
    os.makedirs(config['logging']['save_dir'], exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    experiment_name = f"{config['model']['architecture']}_{timestamp}"
    log_dir = os.path.join(config['logging']['save_dir'], experiment_name)
    
    writer = None
    if config['logging']['tensorboard']:
        writer = SummaryWriter(log_dir)
        print(f"📊 TensorBoard: {log_dir}")
    
    print("\n" + "="*70)
    print("🔄 LOADING DATA")
    print("="*70)
    dataloaders = create_dataloaders(config)
    train_loader = dataloaders['train']
    val_loader = dataloaders['val']
    
    if len(train_loader) == 0:
        print("\n❌ ERROR: No training data found!")
        print(f"   Expected: {config['data']['train_dir']}/glaucoma/ and /normal/")
        print("\n💡 Run: python organize_data.py")
        return
    
    print(f"\n✅ Training batches: {len(train_loader)}")
    print(f"✅ Validation batches: {len(val_loader)}")
    
    print("\n" + "="*70)
    print("🤖 CREATING MODEL")
    print("="*70)
    model = create_model(config)
    model = model.to(device, memory_format=torch.channels_last)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"✅ Architecture: {config['model']['architecture']}")
    print(f"✅ Total parameters: {total_params:,}")
    print(f"✅ Trainable parameters: {trainable_params:,}")
    
    criterion = get_loss_function(config)
    optimizer = optim.AdamW(
        model.parameters(),
        lr=config['training']['learning_rate'],
        weight_decay=config['training']['weight_decay']
    )
    
    # Learning rate scheduler
    if config['training']['scheduler'] == 'cosine':
        scheduler = optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=config['training']['num_epochs'], eta_min=1e-6
        )
    elif config['training']['scheduler'] == 'plateau':
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='max', patience=5, factor=0.5, min_lr=1e-6
        )
    else:
        scheduler = None
    
    early_stopping = EarlyStopping(
        patience=config['training']['early_stopping_patience'],
        mode=config['checkpoint']['mode']
    )
    
    print("\n" + "="*70)
    print("🚀 TRAINING START")
    print("="*70)
    print(f"📈 Epochs: {config['training']['num_epochs']}")
    print(f"📦 Batch size: {config['training']['batch_size']}")
    print(f"🎯 Learning rate: {config['training']['learning_rate']}")
    print(f"⚖️ Weight decay: {config['training']['weight_decay']}")
    print(f"📉 Loss: {config['loss']['type']}")
    print("="*70 + "\n")
    
    best_metric = -float('inf') if config['checkpoint']['mode'] == 'max' else float('inf')
    start_epoch = 0
    patience_counter = 0
    
    for epoch in range(start_epoch, config['training']['num_epochs']):
        epoch_start_time = datetime.now()
        
        print(f"\n{'='*70}")
        print(f"📅 Epoch {epoch+1}/{config['training']['num_epochs']}")
        print(f"{'='*70}")
        
        # Training
        train_loss, train_metrics = train_one_epoch(
            model, train_loader, criterion, optimizer, device, epoch+1,
            gradient_accumulation_steps=1
        )
        
        # Validation
        if len(val_loader) > 0:
            val_loss, val_metrics, val_calc = validate(
                model, val_loader, criterion, device, epoch+1
            )
        else:
            val_loss, val_metrics = train_loss, train_metrics
            val_calc = None
        
        epoch_time = (datetime.now() - epoch_start_time).total_seconds()
        
        # Print metrics
        print(f"\n📊 TRAIN → Loss: {train_loss:.4f} | Acc: {train_metrics['accuracy']:.4f} | "
              f"AUC: {train_metrics['auc']:.4f} | Sens: {train_metrics['sensitivity']:.4f} | "
              f"Spec: {train_metrics['specificity']:.4f}")
        print(f"📊 VAL   → Loss: {val_loss:.4f} | Acc: {val_metrics['accuracy']:.4f} | "
              f"AUC: {val_metrics['auc']:.4f} | Sens: {val_metrics['sensitivity']:.4f} | "
              f"Spec: {val_metrics['specificity']:.4f}")
        print(f"⏱️  Epoch time: {epoch_time:.1f}s")
        
        # TensorBoard logging
        if writer:
            writer.add_scalar('Loss/train', train_loss, epoch)
            writer.add_scalar('Loss/val', val_loss, epoch)
            writer.add_scalar('LR', optimizer.param_groups[0]['lr'], epoch)
            for key in ['accuracy', 'auc', 'sensitivity', 'specificity', 'f1']:
                writer.add_scalar(f'Train/{key}', train_metrics[key], epoch)
                writer.add_scalar(f'Val/{key}', val_metrics[key], epoch)
        
        # Learning rate scheduling
        if scheduler:
            if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                scheduler.step(val_metrics['auc'])
            else:
                scheduler.step()
        
        # Model checkpointing (BEST ONLY)
        monitor_key = config['checkpoint']['monitor'].replace('val_', '')
        monitor_metric = val_metrics[monitor_key]
        is_best = False
        
        if config['checkpoint']['mode'] == 'max':
            if monitor_metric > best_metric:
                best_metric = monitor_metric
                is_best = True
                patience_counter = 0
            else:
                patience_counter += 1
        else:
            if monitor_metric < best_metric:
                best_metric = monitor_metric
                is_best = True
                patience_counter = 0
            else:
                patience_counter += 1
        
        if is_best:
            save_path = os.path.join(config['checkpoint']['save_dir'], 'best_model.pth')
            save_checkpoint(model, optimizer, epoch+1, val_metrics, save_path)
            print(f"💾 New best model! {config['checkpoint']['monitor']}: {monitor_metric:.4f}")
        
        # Early stopping
        if early_stopping(monitor_metric):
            if early_stopping.early_stop:
                print(f"\n⏹️  Early stopping triggered after {epoch+1} epochs")
                print(f"   Best {config['checkpoint']['monitor']}: {best_metric:.4f}")
                break
    
    # Final evaluation
    print("\n" + "="*70)
    print("🎯 FINAL EVALUATION")
    print("="*70)
    
    best_model_path = os.path.join(config['checkpoint']['save_dir'], 'best_model.pth')
    if os.path.exists(best_model_path):
        checkpoint = torch.load(best_model_path, map_location='cpu', weights_only=False)
        model.load_state_dict(checkpoint['model_state_dict'])
        print(f"\n✅ Loaded best model: {best_model_path}")
        print(f"   Best {config['checkpoint']['monitor']}: {best_metric:.4f}")
    
    test_loader = dataloaders['test']
    if len(test_loader) > 0:
        print(f"\n🧪 Testing on {len(test_loader.dataset)} images...")
        test_loss, test_metrics, test_calc = validate(
            model, test_loader, criterion, device, 'Test'
        )
        
        print(f"\n📊 TEST RESULTS:")
        print(f"   Loss: {test_loss:.4f}")
        print(f"   Accuracy: {test_metrics['accuracy']:.4f}")
        print(f"   AUC: {test_metrics['auc']:.4f}")
        print(f"   Sensitivity: {test_metrics['sensitivity']:.4f}")
        print(f"   Specificity: {test_metrics['specificity']:.4f}")
        print(f"   F1 Score: {test_metrics['f1']:.4f}")
        print(f"   Precision: {test_metrics['precision']:.4f}")
        
        # Find optimal threshold
        if len(test_calc.probabilities) > 0:
            print(f"\n🎯 Finding optimal threshold...")
            optimal_threshold = test_calc.find_threshold_at_specificity(
                target_spec=config['evaluation']['target_specificity']
            )
            
            # Save plots
            preds = (np.array(test_calc.probabilities) >= optimal_threshold).astype(int)
            plot_confusion_matrix(
                test_calc.labels, preds,
                save_path=os.path.join(config['checkpoint']['save_dir'], 'confusion_matrix.png')
            )
            plot_roc_curve(
                test_calc.labels, test_calc.probabilities,
                save_path=os.path.join(config['checkpoint']['save_dir'], 'roc_curve.png')
            )
            
            # Save metrics log
            log_metrics(test_metrics, os.path.join(config['checkpoint']['save_dir'], 'metrics.txt'))
    
    # Export optimized model
    print("\n" + "="*70)
    print("📦 EXPORTING MODEL")
    print("="*70)
    model.eval()
    model = optimize_for_cpu(model, quantize=config['cpu']['quantize_model'])
    
    torchscript_path = os.path.join(config['checkpoint']['save_dir'], 'model_scripted.pt')
    export_to_torchscript(
        model, torchscript_path,
        example_input_size=(1, 3, config['data']['image_size'], config['data']['image_size'])
    )
    
    config_path = os.path.join(config['checkpoint']['save_dir'], 'config.yaml')
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    print(f"✅ Config saved: {config_path}")
    
    if writer:
        writer.close()
    
    print("\n" + "="*70)
    print("✅ TRAINING COMPLETE!")
    print("="*70)
    print(f"\n📁 Model saved: {best_model_path}")
    print(f"📁 TorchScript: {torchscript_path}")
    print(f"📊 Best {config['checkpoint']['monitor']}: {best_metric:.4f}")
    print("\n🚀 Ready for deployment!")
    print("   Run: cd ../api && python main.py")
    print("="*70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config/config.yaml')
    parser.add_argument('--resume', type=str, default=None)
    args = parser.parse_args()
    
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    print("=" * 60)
    print("Glaucoma Detection Training")
    print("=" * 60)
    print(f"Model: {config['model']['architecture']}")
    print(f"Image size: {config['data']['image_size']}")
    print(f"Batch size: {config['training']['batch_size']}")
    print(f"Epochs: {config['training']['num_epochs']}")
    print("=" * 60)
    
    train(config, resume_from=args.resume)