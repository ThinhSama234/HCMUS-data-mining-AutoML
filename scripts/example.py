from flaml import AutoML
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split

X, y = load_breast_cancer(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

automl = AutoML()
automl.fit(X_train, y_train, task="classification", time_budget=30)  # 30 seconds

print("Best model:", automl.best_estimator)
print("Best config:", automl.best_config)
print("Accuracy:", automl.score(X_test, y_test))

