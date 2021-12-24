import torch
import numpy as np
import pandas as pd
from transformers import AutoTokenizer, AutoModelForPreTraining, BertForSequenceClassification
import re
import asyncio
import threading

model = None
tokenizer = None
device = None
model_semaphore = threading.Semaphore(1)


def load(path):
    global model, tokenizer, device
    # If there's a GPU available...
    if torch.cuda.is_available():    

        # Tell PyTorch to use the GPU.    
        device = torch.device("cuda")

        print('There are %d GPU(s) available.' % torch.cuda.device_count())

        print('We will use the GPU:', torch.cuda.get_device_name(0))

    # If not...
    else:
        print('No GPU available, using the CPU instead.')
        device = torch.device("cpu")

    model = BertForSequenceClassification.from_pretrained(
        path, # Use the 12-layer BERT model, with an uncased vocab.
        num_labels = 2, # The number of output labels--2 for binary classification.
                        # You can increase this for multi-class tasks.   
        output_attentions = False, # Whether the model returns attentions weights.
        output_hidden_states = False, # Whether the model returns all hidden-states.
    )

    # Load the BERT tokenizer.
    print('Loading BERT tokenizer...')
    tokenizer = AutoTokenizer.from_pretrained(path, do_lower_case=True)

    # Tell pytorch to run this model on the GPU.
    model.to(device)

def preprocess(sentence: str) -> str:
    sentence = re.sub(re.compile(r"<[^>]*>"), " ", sentence)
    sentence = re.sub(re.compile(r"^\[id\d*|.*\],*\s*"), "", sentence)
    sentence = re.sub(re.compile(r"(&quot;)|(&lt;)|(&gt;)|(&amp;)|(&apos;)"), " ", sentence)
    sentence = re.sub(re.compile(
        r"https?://(www\.)?[-a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_+.~#?&/=]*)")," ", sentence)
    sentence = re.sub(re.compile(r"\[[^\[\]]+\|([^\[\]]+)\]"), r"\1", sentence)
    sentence = re.sub(re.compile(r"(&#\d+;)"), " ", sentence)
    sentence = re.sub(re.compile(r"[(_#*=^/`@«»©…“•—<>\[\]\"'+%|&]"), " ", sentence)
    sentence = re.sub(re.compile(r"[.,!?\;:)(_#*=^/`@«»©…“•—<>\[\]\"'+%|&]"), " ", sentence)
    sentence = sentence.replace("  ", " ")
    sentence = sentence.replace("--", " ")
    sentence = sentence.replace('\n', ' ')
    sentence = re.sub("\s\s+", " ", sentence)
    sentence = sentence.lower()
    return sentence


def score(sentence: str):
    global model_semaphore
    with torch.no_grad():
        input_ids = tokenizer.encode_plus(
                        sentence,
                        add_special_tokens=True,
                        max_length=128,
                        padding='max_length',
                        return_attention_mask=False,
                        return_tensors='pt'
                    )
        model_semaphore.acquire()    
        input_ids = input_ids.to(device)
        if len(input_ids["input_ids"][0]) > 128:
            return 0
        result = model(**input_ids)
        answer = result['logits'].softmax(1).to('cpu').detach().numpy()
        model_semaphore.release()
        return answer[0][1]

