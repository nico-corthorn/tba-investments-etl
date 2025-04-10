# Install necessary packages
#!pip install transformers torch accelerate>=0.26.0 s3fs boto3 psycopg2-binary

from ast import literal_eval

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from utils import aws, sql_manager, utils

from tbainvestetl.domain_models.io import convert_dict_to_sql_params

# Define model repo and token
repo_id = "meta-llama/Llama-3.1-8B-Instruct"

# Get HuggingFace token
hf_token = literal_eval(aws.get_secret("prod/HuggingFace/key"))["hf-llama-token"]

# Load the tokenizer
tokenizer = AutoTokenizer.from_pretrained(repo_id, use_auth_token=hf_token)

# Load the model with device_map="auto"
model = AutoModelForCausalLM.from_pretrained(
    repo_id,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto",  # Automatically choose GPU/CPU
    use_auth_token=hf_token,
)

# Check if model is on GPU or CPU
device = "cuda" if torch.cuda.is_available() else "cpu"
# model.to(device)
print(f"Model loaded on: {model.device}")

# SQL setup
sql_params = convert_dict_to_sql_params(literal_eval(aws.get_secret("prod/awsportfolio/key")))
sql = sql_manager.ManagerSQL(db_credentials)

# Get NYT news for year-month period
year_month = "200605"
nyt = sql.select_query(f"select * from nyt_archive where year_month = '{year_month}'")
headline = nyt.iloc[22].headline
snippet = nyt.iloc[22].snippet
print(headline)
print(snippet)

# Prompt to determine sentiment
prompt = f"""
You are a financial analyst tasked with analyzing news about a specific company. For each news headline and snippet, your job is to determine whether the news is positive, neutral, negative, or unknown for the company's future and its stock price in particular. Respond only with one of these three words: "positive", "neutral", "negative", or "unknown".

Here is the criteria for each label:
- positive: the news is likely to have a positive impact on the stock price
- neutral: the news is likely to have no impact on the stock price
- negative: the news is likely to have a negative impact on the stock price
- unknown: the impact of the news is unclear without further information

Provide no explanations, code, or additional information—just the single word answer.

Here are some examples:

News Input:

Credit Suisse Profit Rose 36% in Quarter
The figures beat estimates because costs were lower than expected at the investment bank and revenue was higher.

Answer:
positive

News Input:

Apple Confirms November Event
Apple has confirmed it will hold a product launch event on November 1st, but provided no details about what will be announced.

Answer:
neutral

News Input:

Merck Admits a Data Error on Vioxx
Merck said that it erred when it reported in early 2005 that a crucial statistical test showed that Vioxx caused heart problems only after 18 months of continuous use.

Answer:
negative

News Input:

Profit Falls as Sales Rise at Verizon
Verizon said its profit dipped as it absorbed the costs of integrating MCI and building a fiber optic network designed to deliver television to homes.

Answer:
negative

News Input:

Ford May Produce Its Own Reality TV Show
Ford is pitching a reality show where aspiring car designers would compete to design the next hot Ford vehicle.

Answer:
unknown

Now, analyze this new input:

News Input:
{headline}
{snippet}

Answer:

Answer only positive, neutral, or negative.
"""

# Tokenize the input prompt
inputs = tokenizer(prompt, return_tensors="pt").to(device)

# Generate output from the model
# First two tokens are enough to describe positive, neutral, or negative
with torch.no_grad():
    output = model.generate(**inputs, max_new_tokens=2, pad_token_id=tokenizer.eos_token_id)

# Decode the generated tokens into text
generated_tokens = output[0][inputs["input_ids"].shape[1] :]
generated_text = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

print("Generated Text:")
print(generated_text)
