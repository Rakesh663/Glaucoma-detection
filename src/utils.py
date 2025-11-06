"""
Utility functions for training and evaluation
"""
import torch
import torch.nn as nn
import numpy as np
from sklearn.metrics import (
    roc_auc_score, accuracy_score, precision_recall_fscore_support,
    confusion_matrix, roc_curve
)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns


class FocalLoss(nn.Module):
    """Focal Loss for handling class imbalance"""
    
    def __init__(self, alpha=1.0, gamma=2.0):
        super(FocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma
        
    def forward(self, inputs, targets):
        bce_loss = nn.functional.binary_cross_entropy_with_logits(
            inputs, targets, reduction='none'
        )
        pt = torch.exp(-bce_loss)
        focal_loss = self.alpha * (1 - pt) ** self.gamma * bce_loss
        return focal_loss.mean()


def get_loss_function(config):
    """Get loss function based on config"""
    loss_type = config['loss']['type']
    
    if loss_type == 'bce':
        return nn.BCEWithLogitsLoss()
    elif loss_type == 'focal':
        gamma = config['loss']['focal_gamma']
        return FocalLoss(gamma=gamma)
    else:
        raise ValueError(f"Unknown loss type: {loss_type}")


class MetricsCalculator:
    """Calculate and track metrics"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.predictions = []
        self.labels = []
        self.probabilities = []
    
    def update(self, probs, labels):
        probs = probs.detach().cpu().numpy().flatten()
        labels = labels.detach().cpu().numpy().flatten()
        
        self.probabilities.extend(probs.tolist())
        self.labels.extend(labels.tolist())
    
    def compute(self, threshold=0.5):
        probs = np.array(self.probabilities)
        labels = np.array(self.labels)
        preds = (probs >= threshold).astype(int)
        
        accuracy = accuracy_score(labels, preds)
        
        try:
            auc = roc_auc_score(labels, probs)
        except ValueError:
            auc = 0.0
        
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, preds, average='binary', zero_division=0
        )
        
        tn, fp, fn, tp = confusion_matrix(labels, preds).ravel()
        
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        
        return {
            'accuracy': accuracy,
            'auc': auc,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'sensitivity': sensitivity,
            'specificity': specificity,
            'tp': int(tp),
            'tn': int(tn),
            'fp': int(fp),
            'fn': int(fn)
        }
    
    def find_threshold_at_specificity(self, target_spec=0.95):
        probs = np.array(self.probabilities)
        labels = np.array(self.labels)
        
        fpr, tpr, thresholds = roc_curve(labels, probs)
        specificities = 1 - fpr
        
        idx = np.argmin(np.abs(specificities - target_spec))
        optimal_threshold = thresholds[idx]
        actual_specificity = specificities[idx]
        actual_sensitivity = tpr[idx]
        
        print(f"Threshold for {target_spec:.2%} specificity: {optimal_threshold:.4f}")
        print(f"Actual specificity: {actual_specificity:.2%}")
        print(f"Actual sensitivity: {actual_sensitivity:.2%}")
        
        return float(optimal_threshold)


def plot_confusion_matrix(labels, predictions, save_path=None):
    """Plot confusion matrix"""
    cm = confusion_matrix(labels, predictions)
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(
        cm, annot=True, fmt='d', cmap='Blues',
        xticklabels=['Normal', 'Glaucoma'],
        yticklabels=['Normal', 'Glaucoma']
    )
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.title('Confusion Matrix')
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Confusion matrix saved: {save_path}")
    
    plt.close()


def plot_roc_curve(labels, probabilities, save_path=None):
    """Plot ROC curve"""
    fpr, tpr, _ = roc_curve(labels, probabilities)
    auc = roc_auc_score(labels, probabilities)
    
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, label=f'ROC Curve (AUC = {auc:.3f})', linewidth=2)
    plt.plot([0, 1], [0, 1], 'k--', label='Random Classifier')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve')
    plt.legend(loc='lower right')
    plt.grid(alpha=0.3)
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"ROC curve saved: {save_path}")
    
    plt.close()


class EarlyStopping:
    """Early stopping"""
    
    def __init__(self, patience=10, mode='max', min_delta=0.0):
        self.patience = patience
        self.mode = mode
        self.min_delta = min_delta
        self.counter = 0
        self.best_score = None
        self.early_stop = False
        
        if mode == 'min':
            self.monitor_op = np.less
            self.best_score = np.Inf
        else:
            self.monitor_op = np.greater
            self.best_score = -np.Inf
    
    def __call__(self, score):
        if self.monitor_op(score, self.best_score + self.min_delta):
            self.best_score = score
            self.counter = 0
            return True
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
            return False


def save_checkpoint(model, optimizer, epoch, metrics, save_path):
    """Save model checkpoint"""
    checkpoint = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'metrics': metrics
    }
    torch.save(checkpoint, save_path)
    print(f"Checkpoint saved: {save_path}")


def load_checkpoint(model, checkpoint_path, optimizer=None):
    """Load model checkpoint"""
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    
    if optimizer is not None:
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    
    epoch = checkpoint.get('epoch', 0)
    metrics = checkpoint.get('metrics', {})
    
    print(f"Checkpoint loaded: {checkpoint_path}")
    print(f"Epoch: {epoch}, Metrics: {metrics}")
    
    return model, optimizer, epoch, metrics


def log_metrics(metrics, save_path):
    """Save metrics to text file"""
    with open(save_path, 'w') as f:
        f.write("=" * 50 + "\n")
        f.write("GLAUCOMA DETECTION - TEST METRICS\n")
        f.write("=" * 50 + "\n\n")
        
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                f.write(f"{key:20s}: {value:.4f}\n")
            else:
                f.write(f"{key:20s}: {value}\n")
        
        f.write("\n" + "=" * 50 + "\n")
    
    print(f"Metrics saved: {save_path}")