"""
Quick Start Training Script
Run this to start training immediately
"""
import subprocess
import sys
import os

def check_data():
    """Check if data is organized"""
    if not os.path.exists('data/train/glaucoma'):
        print("❌ ERROR: Training data not found!")
        print("\n💡 Run first: python organize_data.py")
        return False
    
    # Count images
    glaucoma_train = len([f for f in os.listdir('data/train/glaucoma') 
                          if f.endswith(('.jpg', '.jpeg', '.png'))])
    normal_train = len([f for f in os.listdir('data/train/normal') 
                        if f.endswith(('.jpg', '.jpeg', '.png'))])
    
    if glaucoma_train == 0 or normal_train == 0:
        print("❌ ERROR: No images found in training folders!")
        print("\n💡 Run first: python organize_data.py")
        return False
    
    print(f"✅ Training data ready: {glaucoma_train} glaucoma + {normal_train} normal")
    return True

def main():
    print("="*70)
    print("🚀 GLAUCOMA DETECTION - TRAINING")
    print("="*70)
    print()
    
    # Check data
    if not check_data():
        sys.exit(1)
    
    # Run training
    print("\n" + "="*70)
    print("Starting training...")
    print("="*70 + "\n")
    
    try:
        subprocess.run([sys.executable, 'src/train.py'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Training failed with error code {e.returncode}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Training interrupted by user")
        sys.exit(0)

if __name__ == "__main__":
    main()