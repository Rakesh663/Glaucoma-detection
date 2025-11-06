"""
Inference engine for glaucoma detection
"""
import os
import torch
import numpy as np
from PIL import Image
import albumentations as A
from albumentations.pytorch import ToTensorV2
import yaml


class GlaucomaDetector:
    """Production inference engine"""
    
    def __init__(self, model_path, config_path=None, device='cpu'):
        self.device = torch.device(device)
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {
                'data': {'image_size': 640},
                'augmentation': {
                    'normalize': {
                        'mean': [0.485, 0.456, 0.406],
                        'std': [0.229, 0.224, 0.225]
                    }
                },
                'evaluation': {'threshold': 0.5}
            }
        
        self._setup_cpu_optimization()
        
        print(f"Loading model: {model_path}")
        self.model = self._load_model(model_path)
        self.model.eval()
        
        self.transform = self._get_transform()
        print("GlaucomaDetector initialized")
    
    def _setup_cpu_optimization(self):
        num_threads = min(8, os.cpu_count() or 8)
        os.environ["OMP_NUM_THREADS"] = str(num_threads)
        os.environ["MKL_NUM_THREADS"] = str(num_threads)
        torch.set_num_threads(num_threads)
        
        if torch.backends.mkldnn.is_available():
            torch.backends.mkldnn.enabled = True
    
    def _load_model(self, model_path):
        if model_path.endswith('.pt') and 'scripted' in model_path:
            model = torch.jit.load(model_path, map_location=self.device)
        else:
            from model import create_model, optimize_for_cpu
            
            model = create_model(self.config)
            checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)

            if 'model_state_dict' in checkpoint:
                model.load_state_dict(checkpoint['model_state_dict'])
            else:
                model.load_state_dict(checkpoint)
            
            model = optimize_for_cpu(model, quantize=False)
        
        return model.to(self.device)
    
    def _get_transform(self):
        image_size = self.config['data']['image_size']
        mean = self.config['augmentation']['normalize']['mean']
        std = self.config['augmentation']['normalize']['std']
        
        return A.Compose([
            A.Resize(image_size, image_size),
            A.Normalize(mean=mean, std=std),
            ToTensorV2()
        ])
    
    def preprocess(self, image):
        if isinstance(image, Image.Image):
            image = np.array(image.convert('RGB'))
        
        augmented = self.transform(image=image)
        image_tensor = augmented['image']
        image_tensor = image_tensor.unsqueeze(0)
        image_tensor = image_tensor.to(self.device, memory_format=torch.channels_last)
        
        return image_tensor
    
    @torch.no_grad()
    def predict(self, image, return_confidence=True):
        if isinstance(image, str):
            image = Image.open(image).convert('RGB')
        
        image_tensor = self.preprocess(image)
        logits = self.model(image_tensor)
        prob = torch.sigmoid(logits).item()
        
        threshold = self.config['evaluation']['threshold']
        prediction = int(prob >= threshold)
        
        result = {
            'prediction': prediction,
            'label': 'glaucoma' if prediction == 1 else 'normal',
            'confidence': prob if prediction == 1 else (1 - prob)
        }
        
        if return_confidence:
            result['probability'] = prob
            result['risk_level'] = self._get_risk_level(prob)
        
        return result
    
    def _get_risk_level(self, prob):
        if prob < 0.3:
            return "Low Risk"
        elif prob < 0.7:
            return "Moderate Risk"
        else:
            return "High Risk"
    
    @torch.no_grad()
    def predict_batch(self, images, batch_size=16):
        results = []
        
        for i in range(0, len(images), batch_size):
            batch = images[i:i+batch_size]
            batch_tensors = []
            
            for img in batch:
                if isinstance(img, str):
                    img = Image.open(img).convert('RGB')
                batch_tensors.append(self.preprocess(img))
            
            batch_tensor = torch.cat(batch_tensors, dim=0)
            logits = self.model(batch_tensor)
            probs = torch.sigmoid(logits).squeeze().cpu().numpy()
            
            if isinstance(probs, np.float32):
                probs = [probs]
            
            threshold = self.config['evaluation']['threshold']
            for prob in probs:
                prob = float(prob)
                prediction = int(prob >= threshold)
                results.append({
                    'prediction': prediction,
                    'label': 'glaucoma' if prediction == 1 else 'normal',
                    'probability': prob,
                    'confidence': prob if prediction == 1 else (1 - prob),
                    'risk_level': self._get_risk_level(prob)
                })
        
        return results
    
    def get_recommendations(self, prediction_result):
        prob = prediction_result['probability']
        
        if prob < 0.3:
            return [
                "No signs of glaucoma detected",
                "Continue routine annual eye examinations",
                "Maintain healthy lifestyle and diet",
                "Monitor for any vision changes"
            ]
        elif prob < 0.7:
            return [
                "Possible early indicators detected",
                "Schedule comprehensive eye examination within 1-2 months",
                "Visual field testing recommended",
                "Monitor intraocular pressure regularly",
                "Follow up with ophthalmologist"
            ]
        else:
            return [
                "Strong indicators of glaucoma detected",
                "URGENT: Consult ophthalmologist within 1 week",
                "Comprehensive eye examination required",
                "Intraocular pressure measurement essential",
                "Early treatment critical to prevent vision loss"
            ]