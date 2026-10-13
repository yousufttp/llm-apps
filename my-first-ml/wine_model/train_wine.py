import csv
import json

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

X = []  # Wine measurements
y = []  # Known wine classes

with open("wine.data", newline="") as file:
    for row in csv.reader(file):
        y.append(int(row[0]))                  # First column: class
        X.append([float(value) for value in row[1:]])  # Remaining 13 columns

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

print("Test accuracy:", model.score(X_test, y_test))

joblib.dump(model, "wine_model.joblib")
print("Saved trained model to wine_model.joblib")

# Save one held-aside example so another script can try it.
with open("sample_wine.json", "w") as file:
    json.dump({"measurements": X_test[0], "actual_class": y_test[0]}, file)

print("Saved a test example to sample_wine.json")