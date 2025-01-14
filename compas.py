# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn import preprocessing
from torch import nn, optim
import torch.nn.functional as F
import torch.utils.data as data
from torch.utils.data import DataLoader
from torch.utils.data import Dataset
import torch
from torch.autograd import Variable
from sklearn.tree import DecisionTreeClassifier
from sklearn import tree
from sklearn.ensemble import RandomForestClassifier

"""COMPAS.ipynb
Auditor of neural network to find disparate impact
"""

"""
!wget https://raw.githubusercontent.com/propublica/compas-analysis/master/compas-scores.csv

"""


df = pd.read_csv("compas-scores.csv")
df = df.fillna(-1)
dropFeats = ["decile_score", "id", "name", "first",
             "last", "c_case_number", "r_case_number",
             "vr_case_number", "v_type_of_assessment",
             "type_of_assessment", "screening_date",
             "v_screening_date", "score_text"]
df = df.drop(dropFeats, axis=1)
df['compas_screening_date'] = df['compas_screening_date'].astype(
    'datetime64').astype(int)/100000000000
df['dob'] = df['dob'].astype('datetime64').astype(int)/100000000000
df['c_jail_in'] = df['c_jail_in'].astype('datetime64').astype(int)/100000000000
df['c_jail_out'] = df['c_jail_out'].astype(
    'datetime64').astype(int)/100000000000
df['c_offense_date'] = df['c_offense_date'].astype(
    'datetime64').astype(int)/100000000000
df['c_arrest_date'] = df['c_arrest_date'].astype(
    'datetime64').astype(int)/100000000000
df['r_offense_date'] = df['r_offense_date'].astype(
    'datetime64').astype(int)/100000000000
df['r_jail_in'] = df['r_jail_in'].astype(
    'datetime64').astype(int)/100000000000
df['r_jail_out'] = df['r_jail_out'].astype(
    'datetime64').astype(int)/100000000000
df['vr_offense_date'] = df['vr_offense_date'].astype(
    'datetime64').astype(int)/100000000000
df["sex"] = df["sex"].astype('category').cat.codes
df["age_cat"] = df["age_cat"].astype('category').cat.codes
df["race"] = df["race"].astype('category').cat.codes
df["c_charge_degree"] = df["c_charge_degree"].astype('category').cat.codes
df["c_charge_desc"] = df["c_charge_desc"].astype('category').cat.codes
df["r_charge_degree"] = df["r_charge_degree"].astype('category').cat.codes
df["r_charge_desc"] = df["r_charge_desc"].astype('category').cat.codes
df["vr_charge_degree"] = df["vr_charge_degree"].astype('category').cat.codes
df["vr_charge_desc"] = df["vr_charge_desc"].astype('category').cat.codes
df["v_score_text"] = df["v_score_text"].astype('category').cat.codes
df.head()

y = df['decile_score.1']
protectedAttr = ["sex", "race", "dob", "age"]
X = df.drop(['decile_score.1'], axis=1)
X.head()

cleanX = X.drop(protectedAttr, axis=1)
# returns a numpy array
x = cleanX.values
min_max_scaler = preprocessing.MinMaxScaler()
x_scaled = min_max_scaler.fit_transform(x)
cleanX = pd.DataFrame(x_scaled)
cleanX.head()

fixLablesDict = {
    -1: 1,
    }

y = y.replace(fixLablesDict)

X_train, X_test, y_train, y_test = train_test_split(
    cleanX, y, test_size=0.33, random_state=42)


class normY(object):
    def __init__(self, bias=-1):
        self.bias = bias

    def __call__(self, sample):
        x = sample[0]
        y = sample[1]
        y = y + self.bias
        sample = x, y
        return sample


class Compas(Dataset):
    def __init__(self, trainX, trainY, transform=None):
        self.x = trainX.values
        self.y = trainY.values
        self.len = self.x.shape[0]
        self.transform = transform

    def __getitem__(self, index):
        sample = torch.Tensor(self.x[index].astype(float)), self.y[index]
        if self.transform:
            sample = self.transform(sample)
        return sample

    def __len__(self):
        return self.len


ybias = normY()
compas = Compas(X_train, y_train, transform=ybias)
trainloader = DataLoader(dataset=compas, batch_size=64,
                         shuffle=True)


class Classifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(29, 25)
        self.fc2 = nn.Linear(25, 20)
        self.fc3 = nn.Linear(20, 15)
        self.fc4 = nn.Linear(15, 10)

        self.dropout = nn.Dropout(p=0.2)

    def forward(self, x):
        x = x.view(x.shape[0], -1)

        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.dropout(F.relu(self.fc3(x)))
        x = F.log_softmax(self.fc4(x), dim=1)

        return x


model = Classifier()
criterion = nn.NLLLoss()
optimizer = optim.Adam(model.parameters(), lr=0.003)

for epoch in range(20):
    for i, (people, labels) in enumerate(trainloader):
        people = Variable(people)
        labels = Variable(labels)

        optimizer.zero_grad()
        outputs = model(people)

        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        if (i+1) % 1000 == 0:
            print('Epoch [%d/%d], Iter [%d] Loss: %.4f' % (epoch + 1, 10,
                                                           i+1, loss.item()))

model.eval()
# compasTest = Compas(cleanXTest, y_test, transform=ybias)
test = Variable(torch.Tensor(X_test.values))

pred = model(test)

_, predlabel = torch.max(pred.data, 1)

predlabel = predlabel.tolist()
predlabel = pd.DataFrame(predlabel)
predlabel.index = np.arange(3880) + 1
id = np.arange(3880) + 1
id = pd.DataFrame(id)
id.index = id.index + 1

predlabel = pd.concat([id, predlabel], axis=1)
predlabel.columns = ["Person", "Label"]
predlabel.head()

model.eval()
# compasTest = Compas(cleanXTest, y_test, transform=ybias)
treeTrainSet = Variable(torch.Tensor(X_train.values))

yhat = model(treeTrainSet)

_, yhatLabel = torch.max(yhat.data, 1)

yhatlabel = yhatLabel.tolist()
yhatLabel = pd.DataFrame(yhatLabel)
yhatLabel.index = np.arange(7877) + 1
id2 = np.arange(7877) + 1
id2 = pd.DataFrame(id2)
id2.index = id2.index + 1

yhatLabel = pd.concat([id2, yhatLabel], axis=1)
yhatLabel.columns = ["Person", "Label"]
yhatLabel.head()

del model

clf = tree.DecisionTreeClassifier()
X_train_bias, X_test_bias, y_train, y_test = train_test_split(X, y,
                                                              test_size=0.33,
                                                              random_state=42)

clf.fit(X_train_bias, y_train)


totalCorrect = 0
for i in range(len(X_test_bias)):
    if predlabel.iloc[i]['Label'] == y_test.iloc[i]:
        totalCorrect = totalCorrect + 1
print("Acc of nn learning ground truth: ", totalCorrect/3880)


# tree.plot_tree(clf)
totalCorrect = 0
for i in range(len(X_test_bias)):
    predict = clf.predict([X_test_bias.iloc[i]])
    if predict[0] == y_test.iloc[i]:
        totalCorrect = totalCorrect + 1
print("Acc of decision tree learning ground truth: ", totalCorrect/3880)

del clf
del predict

auditor = tree.DecisionTreeClassifier()
auditor.fit(X_train_bias, yhatLabel)
# tree.plot_tree(auditor)

totalCorrect = 0
for i in range(len(X_test_bias)):
    predict = auditor.predict([X_test_bias.iloc[i]])
    if predict[0][1] == predlabel.iloc[i]['Label']:
        totalCorrect = totalCorrect + 1
print("Acc of dec tree with bias feats learning nn: ", totalCorrect/3880)

name = "Auditor.dot"
with open(name, "w") as f:
    f = tree.export_graphviz(auditor, out_file=f)
    i = i + 1

del auditor
del predict

auditorObscured = tree.DecisionTreeClassifier()
auditorObscured.fit(X_train, yhatLabel)
# tree.plot_tree(auditorObscured)

totalCorrect = 0
for i in range(len(X_test)):
    predict = auditorObscured.predict([X_test.iloc[i]])
    if predict[0][1] == predlabel.iloc[i]['Label']:
        totalCorrect = totalCorrect + 1
print("Acc of obscured dec tree learning nn: ", totalCorrect/3880)

name = "AuditorObscured.dot"
with open(name, "w") as f:
    f = tree.export_graphviz(auditorObscured, out_file=f)
    i = i + 1

del auditorObscured
del predict


forest = RandomForestClassifier(n_estimators=3, random_state=0,
                                max_depth=5, n_jobs=1)
forest.fit(X_train_bias, yhatLabel)

totalCorrect = 0
for i in range(len(X_test_bias)):
    predict = forest.predict([X_test_bias.iloc[i]])
    if predict[0][1] == predlabel.iloc[i]['Label']:
        totalCorrect = totalCorrect + 1
print("Acc Random Forest with bias learning nn: ", totalCorrect/3880)

i = 0
for estimator in forest.estimators_:
    name = "treeOut" + str(i) + ".dot"
    with open(name, "w") as f:
        f = tree.export_graphviz(estimator, out_file=f)
        i = i + 1

del forest
del predict
forestObscured = RandomForestClassifier(
    n_estimators=5, random_state=0, max_depth=5)
forestObscured.fit(X_train, yhatLabel)

totalCorrect = 0
for i in range(len(X_test)):
    predict = forestObscured.predict([X_test.iloc[i]])
    if predict[0][1] == predlabel.iloc[i]['Label']:
        totalCorrect = totalCorrect + 1
print("Acc Random Forest obscured learning nn: ", totalCorrect/3880)

i = 0
for estimator in forestObscured.estimators_:
    name = "treeOutObscured" + str(i) + ".dot"
    with open(name, "w") as f:
        f = tree.export_graphviz(estimator, out_file=f)
        i = i + 1

del forestObscured
