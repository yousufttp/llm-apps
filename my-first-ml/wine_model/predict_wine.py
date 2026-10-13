import json
import joblib

model = joblib.load("wine_model.joblib")

with open("sample_wine.json") as file:
    sample = json.load(file)

prediction = model.predict([sample["measurements"]])[0]

print("Predicted class:", prediction)
print("Actual class:", sample["actual_class"])