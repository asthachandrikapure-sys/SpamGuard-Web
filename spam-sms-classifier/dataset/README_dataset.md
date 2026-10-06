# Dataset Instructions

## Required Dataset: SMS Spam Collection

Place the SMS Spam Collection dataset as `spam.csv` in this directory.

### Option 1: Download from UCI Repository
Download from: https://archive.ics.uci.edu/ml/datasets/SMS+Spam+Collection

### Option 2: Download from Kaggle
https://www.kaggle.com/datasets/uciml/sms-spam-collection-dataset

The file should be named `spam.csv` and contain at minimum two columns:
- `v1`: Label column (ham/spam)
- `v2`: Message column (the SMS text)

### Sample Format
```
v1,v2
ham,"Go until jurong point, crazy.. Available only in bugis n great world la e buffet..."
spam,Free entry in 2 a wkly comp to win FA Cup final tkts 21st May 2005...
ham,Ok lar... Joking wif u oni...
```

A sample dataset is included in `sample_spam.csv` for initial testing.
If you use the full dataset, rename or replace it as `spam.csv`.
