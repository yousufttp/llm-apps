from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

flowers = load_iris()
X_train, X_test, y_train, y_test = train_test_split(
    flowers.data, flowers.target, test_size=0.2, random_state=42
)

model = DecisionTreeClassifier(random_state=42)
model.fit(X_train, y_train)

print("Test accuracy:", model.score(X_test, y_test))

sample = X_test[1]
prediction = model.predict([sample])[0]
print("Measurements:", sample)
print("Predicted flower:", flowers.target_names[prediction])
print("Actual flower:", flowers.target_names[y_test[1]])