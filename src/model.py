"""
Clinical-Grade Glaucoma Detection Model
Production-ready with ensemble, attention, uncertainty, and explainability

Key Features:
1. Ensemble Architecture (multiple backbones for robustness)
2. Spatial Attention (focus on optic disc region)
3. Monte Carlo Dropout (uncertainty estimation)
4. Grad-CAM Explainability (visual explanations for doctors)
5. CPU Optimization (production deployment)
"""

import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import timm
import numpy as np
from typing import Dict, List, Tuple, Optional, Union
from PIL import Image
import warnings


class SpatialAttention(nn.Module):
    """
    Spatial attention module to focus on relevant regions (optic disc).
    Provides interpretable attention maps for doctors.
    """
    
    def __init__(self, in_channels: int, reduction: int = 16):
        super().__init__()
        
        # Channel attention
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        
        self.fc = nn.Sequential(
            nn.Linear(in_channels, in_channels // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(in_channels // reduction, in_channels, bias=False),
            nn.Sigmoid()
        )
        
        # Spatial attention
        self.conv = nn.Sequential(
            nn.Conv2d(2, 1, kernel_size=7, padding=3, bias=False),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Apply spatial attention.
        
        Returns:
            Attended features and attention map
        """
        b, c, h, w = x.size()
        
        # Channel attention
        avg_out = self.fc(self.avg_pool(x).view(b, c))
        max_out = self.fc(self.max_pool(x).view(b, c))
        channel_attention = (avg_out + max_out).view(b, c, 1, 1)
        x = x * channel_attention
        
        # Spatial attention
        avg_spatial = torch.mean(x, dim=1, keepdim=True)
        max_spatial, _ = torch.max(x, dim=1, keepdim=True)
        spatial_features = torch.cat([avg_spatial, max_spatial], dim=1)
        spatial_attention = self.conv(spatial_features)
        
        attended = x * spatial_attention
        
        return attended, spatial_attention


class GlaucomaClassifier(nn.Module):
    """
    Enhanced binary classifier for glaucoma detection.
    Supports attention and uncertainty estimation.
    """
    
    def __init__(
        self,
        architecture: str = 'efficientnet_b0',
        num_classes: int = 1,
        pretrained: bool = True,
        dropout: float = 0.3,
        use_attention: bool = True,
        mc_dropout: bool = True  # Monte Carlo dropout for uncertainty
    ):
        super().__init__()
        
        self.architecture = architecture
        self.use_attention = use_attention
        self.mc_dropout = mc_dropout
        self.dropout_rate = dropout
        
        # Create backbone
        self.backbone = timm.create_model(
            architecture,
            pretrained=pretrained,
            num_classes=0,
            global_pool=''  # We'll add our own pooling
        )
        
        # Get feature dimensions
        with torch.no_grad():
            dummy_input = torch.randn(1, 3, 224, 224)
            features = self.backbone(dummy_input)
            self.feature_dim = features.shape[1]
            self.feature_size = features.shape[2:]
        
        # Spatial attention
        if self.use_attention:
            self.attention = SpatialAttention(self.feature_dim)
        
        # Global pooling
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        
        # Classifier head with dropout for MC sampling
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(self.feature_dim, 512),
            nn.ReLU(inplace=True),
            nn.BatchNorm1d(512),
            nn.Dropout(dropout / 2),
            nn.Linear(512, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout / 2),
            nn.Linear(256, num_classes)
        )
        
        # Store feature maps for Grad-CAM
        self.feature_maps = None
        self.gradients = None
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor (B, 3, H, W)
            
        Returns:
            Logits (B, 1)
        """
        # Extract features
        features = self.backbone(x)
        self.feature_maps = features  # Store for Grad-CAM
        
        # Apply attention if enabled
        if self.use_attention:
            features, self.attention_map = self.attention(features)
        
        # Global pooling
        pooled = self.global_pool(features)
        pooled = pooled.view(pooled.size(0), -1)
        
        # Classify
        logits = self.classifier(pooled)
        
        return logits
    
    def forward_with_attention(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass returning attention map for visualization.
        """
        features = self.backbone(x)
        
        if self.use_attention:
            features, attention_map = self.attention(features)
        else:
            attention_map = None
        
        pooled = self.global_pool(features)
        pooled = pooled.view(pooled.size(0), -1)
        logits = self.classifier(pooled)
        
        return logits, attention_map
    
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Get probability predictions."""
        logits = self.forward(x)
        probs = torch.sigmoid(logits)
        return probs
    
    def predict_with_uncertainty(
        self,
        x: torch.Tensor,
        n_samples: int = 10
    ) -> Dict[str, torch.Tensor]:
        """
        Predict with uncertainty estimation using Monte Carlo Dropout.
        
        Args:
            x: Input tensor (B, 3, H, W)
            n_samples: Number of MC samples
            
        Returns:
            Dict with mean prediction, std (uncertainty), and samples
        """
        # Enable dropout even during evaluation
        was_training = self.training
        
        # Collect samples
        samples = []
        
        for _ in range(n_samples):
            # Enable dropout layers
            for module in self.modules():
                if isinstance(module, nn.Dropout):
                    module.train()
            
            with torch.no_grad():
                logits = self.forward(x)
                probs = torch.sigmoid(logits)
                samples.append(probs)
        
        # Restore training state
        if not was_training:
            self.eval()
        
        # Stack samples
        samples = torch.stack(samples, dim=0)  # (n_samples, B, 1)
        
        # Compute statistics
        mean = samples.mean(dim=0)
        std = samples.std(dim=0)
        
        # Uncertainty score (higher std = more uncertain)
        uncertainty = std
        
        # Confidence interval (95%)
        ci_low = torch.quantile(samples, 0.025, dim=0)
        ci_high = torch.quantile(samples, 0.975, dim=0)
        
        return {
            'prediction': mean,
            'uncertainty': uncertainty,
            'std': std,
            'ci_low': ci_low,
            'ci_high': ci_high,
            'samples': samples
        }


class GlaucomaEnsemble(nn.Module):
    """
    Ensemble of diverse backbones for robust predictions.
    Combines EfficientNet, ResNet, and ConvNeXt architectures.
    """
    
    def __init__(
        self,
        backbones: List[str] = None,
        num_classes: int = 1,
        pretrained: bool = True,
        dropout: float = 0.3,
        use_attention: bool = True
    ):
        super().__init__()
        
        if backbones is None:
            backbones = ['efficientnet_b0', 'resnet50', 'convnext_tiny']
        
        self.backbones = backbones
        self.n_models = len(backbones)
        
        # Create ensemble members
        self.models = nn.ModuleList([
            GlaucomaClassifier(
                architecture=arch,
                num_classes=num_classes,
                pretrained=pretrained,
                dropout=dropout,
                use_attention=use_attention
            )
            for arch in backbones
        ])
        
        # Learnable weights for ensemble
        self.ensemble_weights = nn.Parameter(torch.ones(self.n_models) / self.n_models)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass with weighted ensemble.
        """
        outputs = []
        
        for model in self.models:
            logits = model(x)
            probs = torch.sigmoid(logits)
            outputs.append(probs)
        
        # Stack outputs
        outputs = torch.stack(outputs, dim=0)  # (n_models, B, 1)
        
        # Weighted average
        weights = F.softmax(self.ensemble_weights, dim=0)
        ensemble_output = (weights.view(-1, 1, 1) * outputs).sum(dim=0)
        
        # Convert back to logits for BCE loss compatibility
        # Clamp to avoid log(0)
        ensemble_output = torch.clamp(ensemble_output, 1e-7, 1 - 1e-7)
        logits = torch.log(ensemble_output / (1 - ensemble_output))
        
        return logits
    
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Get ensemble probability predictions."""
        outputs = []
        
        for model in self.models:
            probs = model.predict_proba(x)
            outputs.append(probs)
        
        outputs = torch.stack(outputs, dim=0)
        weights = F.softmax(self.ensemble_weights, dim=0)
        ensemble_output = (weights.view(-1, 1, 1) * outputs).sum(dim=0)
        
        return ensemble_output
    
    def predict_with_uncertainty(
        self,
        x: torch.Tensor,
        n_samples: int = 10
    ) -> Dict[str, torch.Tensor]:
        """
        Predict with ensemble + MC dropout uncertainty.
        """
        all_samples = []
        
        for model in self.models:
            result = model.predict_with_uncertainty(x, n_samples)
            all_samples.append(result['samples'])
        
        # Combine all samples
        all_samples = torch.cat(all_samples, dim=0)  # (n_models * n_samples, B, 1)
        
        mean = all_samples.mean(dim=0)
        std = all_samples.std(dim=0)
        
        ci_low = torch.quantile(all_samples, 0.025, dim=0)
        ci_high = torch.quantile(all_samples, 0.975, dim=0)
        
        return {
            'prediction': mean,
            'uncertainty': std,
            'std': std,
            'ci_low': ci_low,
            'ci_high': ci_high,
            'samples': all_samples
        }


class GradCAM:
    """
    Grad-CAM for visual explanations.
    Shows which regions the model focuses on for predictions.
    Essential for doctor acceptance - no black box!
    """
    
    def __init__(self, model: nn.Module, target_layer: str = None):
        """
        Initialize Grad-CAM.
        
        Args:
            model: The model to explain
            target_layer: Name of target layer for gradients
        """
        self.model = model
        self.gradients = None
        self.activations = None
        
        # Find target layer
        self._find_target_layer(target_layer)
        
        # Register hooks
        self._register_hooks()
    
    def _find_target_layer(self, target_layer: str = None):
        """Find the target layer for Grad-CAM."""
        if target_layer is not None:
            self.target_layer = self._get_layer_by_name(target_layer)
        else:
            # Default: last convolutional layer in backbone
            if hasattr(self.model, 'backbone'):
                # Find last conv layer
                self.target_layer = None
                for name, module in self.model.backbone.named_modules():
                    if isinstance(module, nn.Conv2d):
                        self.target_layer = module
                        self.target_layer_name = name
            else:
                raise ValueError("Could not find target layer")
    
    def _get_layer_by_name(self, name: str) -> nn.Module:
        """Get layer by name."""
        for n, m in self.model.named_modules():
            if n == name:
                return m
        raise ValueError(f"Layer {name} not found")
    
    def _register_hooks(self):
        """Register forward and backward hooks."""
        def forward_hook(module, input, output):
            self.activations = output.detach()
        
        def backward_hook(module, grad_input, grad_output):
            self.gradients = grad_output[0].detach()
        
        self.target_layer.register_forward_hook(forward_hook)
        self.target_layer.register_full_backward_hook(backward_hook)
    
    def generate(
        self,
        input_tensor: torch.Tensor,
        target_class: int = None
    ) -> np.ndarray:
        """
        Generate Grad-CAM heatmap.
        
        Args:
            input_tensor: Input image tensor (1, 3, H, W)
            target_class: Target class (0 or 1), None for predicted class
            
        Returns:
            Heatmap as numpy array (H, W)
        """
        self.model.eval()
        
        # Enable gradients explicitly (even if we're in a no_grad context)
        with torch.enable_grad():
            # Create tensor with gradients
            input_tensor = input_tensor.clone().detach().requires_grad_(True)
            
            # Forward pass
            output = self.model(input_tensor)
            
            if target_class is None:
                target_class = (torch.sigmoid(output) > 0.5).int().item()
            
            # Backward pass
            self.model.zero_grad()
            
            if target_class == 1:
                output.backward()
            else:
                (-output).backward()
        
        # Get gradients and activations
        gradients = self.gradients
        activations = self.activations
        
        # Global average pooling of gradients
        weights = gradients.mean(dim=(2, 3), keepdim=True)
        
        # Weighted combination of activations
        cam = (weights * activations).sum(dim=1, keepdim=True)
        
        # ReLU
        cam = F.relu(cam)
        
        # Normalize
        cam = cam - cam.min()
        if cam.max() > 0:
            cam = cam / cam.max()
        
        # Resize to input size
        cam = F.interpolate(
            cam,
            size=input_tensor.shape[2:],
            mode='bilinear',
            align_corners=False
        )
        
        return cam.squeeze().cpu().numpy()
    
    def generate_overlay(
        self,
        image: Union[np.ndarray, Image.Image],
        input_tensor: torch.Tensor,
        alpha: float = 0.5
    ) -> np.ndarray:
        """
        Generate Grad-CAM overlay on original image.
        
        Args:
            image: Original image (H, W, 3) uint8
            input_tensor: Preprocessed input tensor
            alpha: Overlay transparency
            
        Returns:
            Overlaid image (H, W, 3) uint8
        """
        import cv2
        
        # Generate heatmap
        heatmap = self.generate(input_tensor)
        
        # Convert image to numpy if needed
        if isinstance(image, Image.Image):
            image = np.array(image)
        
        # Resize heatmap to image size
        heatmap = cv2.resize(heatmap, (image.shape[1], image.shape[0]))
        
        # Convert to colormap
        heatmap_colored = cv2.applyColorMap(
            np.uint8(255 * heatmap),
            cv2.COLORMAP_JET
        )
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
        
        # Overlay
        overlay = cv2.addWeighted(image, 1 - alpha, heatmap_colored, alpha, 0)
        
        return overlay


def create_model(config: Dict, ensemble: bool = False) -> nn.Module:
    """
    Create model from configuration.
    
    Args:
        config: Configuration dictionary
        ensemble: If True, create ensemble model
        
    Returns:
        Model instance
    """
    model_config = config.get('model', {})
    
    if ensemble or model_config.get('use_ensemble', False):
        backbones = model_config.get('backbones', ['efficientnet_b0', 'resnet50'])
        model = GlaucomaEnsemble(
            backbones=backbones,
            num_classes=model_config.get('num_classes', 1),
            pretrained=model_config.get('pretrained', True),
            dropout=model_config.get('dropout', 0.3),
            use_attention=model_config.get('use_attention', True)
        )
    else:
        model = GlaucomaClassifier(
            architecture=model_config.get('architecture', 'efficientnet_b0'),
            num_classes=model_config.get('num_classes', 1),
            pretrained=model_config.get('pretrained', True),
            dropout=model_config.get('dropout', 0.3),
            use_attention=model_config.get('use_attention', True),
            mc_dropout=model_config.get('mc_dropout', True)
        )
    
    return model


def optimize_for_cpu(model: nn.Module, quantize: bool = False) -> nn.Module:
    """
    Optimize model for CPU inference.
    
    Args:
        model: Model to optimize
        quantize: Apply dynamic quantization
        
    Returns:
        Optimized model
    """
    # Set thread count
    num_threads = min(8, os.cpu_count() or 8)
    os.environ["OMP_NUM_THREADS"] = str(num_threads)
    os.environ["MKL_NUM_THREADS"] = str(num_threads)
    torch.set_num_threads(num_threads)
    torch.set_num_interop_threads(max(1, num_threads // 2))
    
    # Enable MKL-DNN if available
    if torch.backends.mkldnn.is_available():
        torch.backends.mkldnn.enabled = True
    
    model.eval()
    
    # Convert to channels_last format
    model = model.to(memory_format=torch.channels_last)
    
    # Dynamic quantization
    if quantize:
        try:
            import torch.ao.quantization as aoq
            model = aoq.quantize_dynamic(
                model,
                {nn.Linear},
                dtype=torch.qint8
            )
        except Exception as e:
            warnings.warn(f"Quantization failed: {e}")
    
    return model


def export_to_torchscript(
    model: nn.Module,
    save_path: str,
    example_input_size: Tuple[int, ...] = (1, 3, 512, 512)
) -> torch.jit.ScriptModule:
    """
    Export model to TorchScript for production deployment.
    
    Args:
        model: Model to export
        save_path: Path to save TorchScript model
        example_input_size: Example input shape
        
    Returns:
        TorchScript model
    """
    model.eval()
    
    example_input = torch.randn(example_input_size)
    example_input = example_input.to(memory_format=torch.channels_last)
    
    with torch.no_grad():
        traced_model = torch.jit.trace(model, example_input)
    
    frozen_model = torch.jit.freeze(traced_model)
    frozen_model.save(save_path)
    
    print(f"TorchScript model saved: {save_path}")
    
    return frozen_model