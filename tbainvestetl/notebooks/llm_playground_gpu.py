#!pip install transformers torch accelerate>=0.26.0 s3fs boto3 psycopg2-binary pandas tqdm

# Install common dependencies and tbainvestetl
#!make install

import re
from ast import literal_eval

import pandas as pd
import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

from tbainvestetl.domain_models.io import convert_dict_to_sql_params
from tbainvestetl.utils import aws, sql_manager, utils


def remove_non_letters_except_spaces(input_string):
    return re.sub(r"[^a-zA-Z\s]", "", input_string)


def create_prompt(headline, snippet):
    """Create a standardized prompt for sentiment analysis."""
    return f"""
You are a financial analyst tasked with analyzing news about a specific company. For each news headline and snippet, your job is to determine whether the news is positive, neutral, negative, or unknown for the company's future and its stock price in particular. Respond only with one of these three words: "positive", "neutral", "negative", or "unknown".

Here is the criteria for each label:
- positive: the news is likely to have a positive impact on the stock price
- neutral: the news is likely to have no impact on the stock price
- negative: the news is likely to have a negative impact on the stock price

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

Ford May Produce Its Own Reality TV Show
Ford is pitching a reality show where aspiring car designers would compete to design the next hot Ford vehicle.

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


Now, analyze this new input:

News Input:
{headline}
{snippet}

Answer:

Answer only positive, neutral, or negative.
"""


def run_sentiment_analysis(nyt_df, model, tokenizer):
    """
    Run sentiment analysis on the entire DataFrame with output validation.

    Args:
        nyt_df (pd.DataFrame): Input DataFrame containing 'headline' and 'snippet' columns
        model: The loaded LLaMA model
        tokenizer: The loaded tokenizer

    Returns:
        pd.DataFrame: Results DataFrame with sentiment analysis
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Valid sentiment labels
    VALID_SENTIMENTS = {"positive", "neutral", "negative"}
    MAX_RETRIES = 3

    results = []

    # Process each article with progress bar
    for idx, row in tqdm(nyt_df.iterrows(), total=len(nyt_df), desc="Processing articles"):
        sentiment = None
        retries = 0

        while sentiment not in VALID_SENTIMENTS and retries < MAX_RETRIES:
            prompt = create_prompt(row["headline"], row["snippet"])

            # Tokenize the input prompt
            inputs = tokenizer(prompt, return_tensors="pt").to(device)

            # Generate output from the model with more tokens to ensure complete response
            with torch.no_grad():
                output = model.generate(
                    **inputs,
                    max_new_tokens=4,
                    do_sample=True,
                    # temperature=0.3,
                    num_return_sequences=1,
                    pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )

            # Decode the generated tokens into text
            generated_tokens = output[0][inputs["input_ids"].shape[1] :]
            original_response = (
                tokenizer.decode(generated_tokens, skip_special_tokens=True).strip().lower()
            )

            # Clean up the response
            # Replace line break
            response = original_response.replace("\n", " ")
            # Remove non-letter characters
            response = remove_non_letters_except_spaces(response)
            # Remove common prefixes that might appear
            prefixes_to_remove = ["answer:", "answer"]
            for prefix in prefixes_to_remove:
                if response.startswith(prefix):
                    response = response[len(prefix) :].strip()

            # Extract the first word as sentiment
            sentiment = response.split()[0] if response else None

            # Validate sentiment
            if sentiment not in VALID_SENTIMENTS:
                retries += 1
                print(
                    f"\nInvalid response '{response}' for article {idx}. Retry {retries}/{MAX_RETRIES}"
                )

        # If still invalid after retries, default to 'neutral'
        if sentiment not in VALID_SENTIMENTS:
            print(
                f"\nWarning: Could not get valid sentiment for article {idx} after {MAX_RETRIES} retries. Default to 'neutral'"
            )
            sentiment = "neutral"

        results.append(
            {
                "id": idx,
                "headline": row["headline"],
                "snippet": row["snippet"],
                "output": original_response,
                "sentiment": sentiment,
                "retries": retries,
            }
        )

        # Clear CUDA cache periodically
        if idx % 100 == 0 and device == "cuda":
            torch.cuda.empty_cache()

    return pd.DataFrame(results)


# Example usage:
if __name__ == "__main__":
    # Your existing setup code here
    repo_id = "meta-llama/Llama-3.1-8B-Instruct"
    hf_token = literal_eval(aws.get_secret("prod/HuggingFace/key"))["hf-llama-token"]

    # Load model and tokenizer
    tokenizer = AutoTokenizer.from_pretrained(repo_id, use_auth_token=hf_token)
    model = AutoModelForCausalLM.from_pretrained(
        repo_id,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
        use_auth_token=hf_token,
    )

    # SQL setup and data retrieval
    sql_params = convert_dict_to_sql_params(literal_eval(aws.get_secret("prod/awsportfolio/key")))
    sql = sql_manager.ManagerSQL(sql_params)

    # Get NYT news for year-month period
    year_month = "200605"
    nyt = sql.select_query(f"select * from nyt_archive where year_month = '{year_month}'")
    nyt = nyt.head()  # TODO: Remove after successful testing

    # Run sentiment analysis
    results_df = run_sentiment_analysis(nyt.head(), model, tokenizer)

    # Print summary statistics
    print("\nSentiment Distribution:")
    print(results_df["sentiment"].value_counts())
