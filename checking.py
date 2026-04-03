from model import load_model
import json
from PIL import Image
import torchvision.transforms as transforms
import torch

# ✅ Load model
model, device = load_model("model.pth")

# ✅ Load labels
with open("labels.json") as f:
    labels = json.load(f)

# ✅ Image transform (FIXED SIZE)
transform = transforms.Compose([
    transforms.Resize((28, 28)),   # 🔥 IMPORTANT FIX
    transforms.ToTensor()
])

# ✅ Load image
image_path = "ISIC_0024310.jpg"   # 👉 change if needed
image = Image.open(image_path).convert("RGB")
image = transform(image).unsqueeze(0).to(device)

# ✅ Prediction
with torch.no_grad():
    output = model(image)
    probabilities = torch.softmax(output, dim=1)
    confidence, predicted = torch.max(probabilities, 1)

# ✅ Output result
predicted_label = labels[str(predicted.item())]

print("Predicted Disease:", predicted_label)
print("Confidence:", round(confidence.item() * 100, 2), "%")