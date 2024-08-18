# -*- coding: utf-8 -*-
"""NER Training _ NLP with HuggingFace Tutorial.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1NsqpyM85aS33EUzEsNzBAuOottERO4D2

## The Dataset
### CONLLPP Dataset

https://huggingface.co/datasets/conllpp

- CoNLLpp is a corrected version of the CoNLL2003 NER dataset where labels of 5.38% of the sentences in the test set have been manually corrected. The original CoNLL2003 dataset is available at https://www.clips.uantwerpen.be/conll2003/ner/.

```
{
    "tokens": ["SOCCER", "-", "JAPAN", "GET", "LUCKY", "WIN", ",", "CHINA", "IN", "SURPRISE", "DEFEAT", "."],
    "original_ner_tags_in_conll2003": ["O", "O", "B-LOC", "O", "O", "O", "O", "B-PER", "O", "O", "O", "O"],
    "corrected_ner_tags_in_conllpp": ["O", "O", "B-LOC", "O", "O", "O", "O", "B-LOC", "O", "O", "O", "O"],
}

```

```
{
    "chunk_tags": [11, 12, 12, 21, 13, 11, 11, 21, 13, 11, 12, 13, 11, 21, 22, 11, 12, 17, 11, 21, 17, 11, 12, 12, 21, 22, 22, 13, 11, 0],
    "id": "0",
    "ner_tags": [0, 3, 4, 0, 0, 0, 0, 0, 0, 7, 0, 0, 0, 0, 0, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "pos_tags": [12, 22, 22, 38, 15, 22, 28, 38, 15, 16, 21, 35, 24, 35, 37, 16, 21, 15, 24, 41, 15, 16, 21, 21, 20, 37, 40, 35, 21, 7],
    "tokens": ["The", "European", "Commission", "said", "on", "Thursday", "it", "disagreed", "with", "German", "advice", "to", "consumers", "to", "shun", "British", "lamb", "until", "scientists", "determine", "whether", "mad", "cow", "disease", "can", "be", "transmitted", "to", "sheep", "."]
}

```

## Coding
"""

!pip install -U transformers
!pip install -U accelerate
!pip install -U datasets

import pandas as pd
from datasets import load_dataset

data = load_dataset('conllpp')
data

data['train'].features

pd.DataFrame(data['train'][:])[['tokens', 'ner_tags']].iloc[0]

tags = data['train'].features['ner_tags'].feature

index2tag = {idx:tag for idx, tag in enumerate(tags.names)}
tag2index = {tag:idx for idx, tag in enumerate(tags.names)}

index2tag

tags.int2str(3)

def create_tag_names(batch):
  tag_name = {'ner_tags_str': [tags.int2str(idx) for idx in batch['ner_tags']]}
  return tag_name

data = data.map(create_tag_names)

pd.DataFrame(data['train'][:])[['tokens', 'ner_tags', 'ner_tags_str']].iloc[0]

"""## Model Building

### Tokenization
"""

from transformers import AutoTokenizer

model_checkpoint = "distilbert-base-cased"
tokenizer = AutoTokenizer.from_pretrained(model_checkpoint)

tokenizer.is_fast

inputs = data['train'][0]['tokens']
inputs = tokenizer(inputs, is_split_into_words=True)
print(inputs.tokens())

print(data['train'][0]['tokens'])
print(data['train'][0]['ner_tags_str'])

inputs.word_ids()

def align_labels_with_tokens(labels, word_ids):
  new_labels = []
  current_word=None
  for word_id in word_ids:
    if word_id != current_word:
      current_word = word_id
      label = -100 if word_id is None else labels[word_id]
      new_labels.append(label)

    elif word_id is None:
      new_labels.append(-100)

    else:
      label = labels[word_id]

      if label%2==1:
        label = label + 1
      new_labels.append(label)

  return new_labels

labels = data['train'][0]['ner_tags']
word_ids = inputs.word_ids()
print(labels, word_ids)

align_labels_with_tokens(labels, word_ids)

def tokenize_and_align_labels(examples):
  tokenized_inputs = tokenizer(examples['tokens'], truncation=True, is_split_into_words=True)

  all_labels = examples['ner_tags']

  new_labels = []
  for i, labels in enumerate(all_labels):
    word_ids = tokenized_inputs.word_ids(i)
    new_labels.append(align_labels_with_tokens(labels, word_ids))

  tokenized_inputs['labels'] = new_labels

  return tokenized_inputs

tokenized_datasets = data.map(tokenize_and_align_labels, batched=True, remove_columns=data['train'].column_names)

tokenized_datasets

"""### Data Collation and Metrics"""

from transformers import DataCollatorForTokenClassification

data_collator = DataCollatorForTokenClassification(tokenizer=tokenizer)

batch = data_collator([tokenized_datasets['train'][i] for i in range(2)])
batch

"""### Metrics"""

!pip install seqeval
!pip install evaluate

import evaluate
metric = evaluate.load('seqeval')

ner_feature = data['train'].features['ner_tags']
ner_feature

label_names = ner_feature.feature.names
label_names

labels = data['train'][0]['ner_tags']
labels = [label_names[i] for i in labels]
labels

predictions = labels.copy()
predictions[2] = "O"

metric.compute(predictions=[predictions], references=[labels])

import numpy as np

def compute_metrics(eval_preds):
  logits, labels = eval_preds

  predictions = np.argmax(logits, axis=-1)

  true_labels = [[label_names[l] for l in label if l!=-100] for label in labels]

  true_predictions = [[label_names[p] for p,l in zip(prediction, label) if l!=-100]
                      for prediction, label in zip(predictions, labels)]

  all_metrics = metric.compute(predictions=true_predictions, references=true_labels)

  return {"precision": all_metrics['overall_precision'],
          "recall": all_metrics['overall_recall'],
          "f1": all_metrics['overall_f1'],
          "accuracy": all_metrics['overall_accuracy']}

"""### Model Training"""

id2label = {i:label for i, label in enumerate(label_names)}
label2id = {label:i for i, label in enumerate(label_names)}

print(id2label)

from transformers import AutoModelForTokenClassification

model = AutoModelForTokenClassification.from_pretrained(
                                                    model_checkpoint,
                                                    id2label=id2label,
                                                    label2id=label2id)

model.config.num_labels

from transformers import TrainingArguments

args = TrainingArguments("distilbert-finetuned-ner",
                         evaluation_strategy = "epoch",
                         save_strategy="epoch",
                         learning_rate = 2e-5,
                         num_train_epochs=3,
                         weight_decay=0.01)

from transformers import Trainer
trainer = Trainer(model=model,
                  args=args,
                  train_dataset = tokenized_datasets['train'],
                  eval_dataset = tokenized_datasets['validation'],
                  data_collator=data_collator,
                  compute_metrics=compute_metrics,
                  tokenizer=tokenizer)

trainer.train()

from transformers import pipeline

checkpoint = "/content/distilbert-finetuned-ner/checkpoint-5268"
token_classifier = pipeline(
    "token-classification", model=checkpoint, aggregation_strategy="simple"
)

token_classifier("My name is Laxmi Kant Tiwari. I work at KGP Talkie and live in Mumbai")

!zip -r distilbert_ner.zip "/content/distilbert-finetuned-ner/checkpoint-5268"








