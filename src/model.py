"""
Glaucoma Detection Model
"""
import os
import torch
import torch.nn as nn
import timm


class GlaucomaClassifier(nn.Module):
    """Binary classifier for glaucoma detection"""
    
    def __init__(self, architecture='efficientnet_b0', num_classes=1, 
                 pretrained=True, dropout=0.3):
        super(GlaucomaClassifier, self).__init__()
        
        self.backbone = timm.create_model(
            architecture,
            pretrained=pretrained,
            num_classes=0,
            global_pool='avg'
        )
        
        with torch.no_grad():
            dummy_input = torch.randn(1, 3, 224, 224)
            features = self.backbone(dummy_input)
            self.feature_dim = features.shape[1]
        
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(self.feature_dim, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout / 2),
            nn.Linear(256, num_classes)
        )
        
    def forward(self, x):
        features = self.backbone(x)
        logits = self.classifier(features)
        return logits
    
    def predict_proba(self, x):
        logits = self.forward(x)
        probs = torch.sigmoid(logits)
        return probs


def create_model(config):
    """Create model from config"""
    model = GlaucomaClassifier(
        architecture=config['model']['architecture'],
        num_classes=config['model']['num_classes'],
        pretrained=config['model']['pretrained'],
        dropout=config['model']['dropout']
    )
    return model


def optimize_for_cpu(model, quantize=False):
    """Optimize model for CPU inference"""
    import torch.ao.quantization as aoq
    
    num_threads = min(8, os.cpu_count() or 8)
    os.environ["OMP_NUM_THREADS"] = str(num_threads)
    os.environ["MKL_NUM_THREADS"] = str(num_threads)
    torch.set_num_threads(num_threads)
    torch.set_num_interop_threads(max(1, num_threads // 2))
    
    if torch.backends.mkldnn.is_available():
        torch.backends.mkldnn.enabled = True
    
    model.eval()
    model = model.to(memory_format=torch.channels_last)
    
    if quantize:
        model.classifier = aoq.quantize_dynamic(
            model.classifier,
            {nn.Linear},
            dtype=torch.qint8
        )
    
    return model


def export_to_torchscript(model, save_path, example_input_size=(1, 3, 640, 640)):
    """Export model to TorchScript"""
    model.eval()
    example_input = torch.randn(example_input_size)
    example_input = example_input.to(memory_format=torch.channels_last)
    
    with torch.no_grad():
        traced_model = torch.jit.trace(model, example_input)
    frozen_model = torch.jit.freeze(traced_model)
    frozen_model.save(save_path)
    print(f"TorchScript model saved: {save_path}")
    
    return frozen_model