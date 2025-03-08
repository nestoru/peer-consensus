#!/usr/bin/env python3
"""
run_discussion.py

Command-line tool to run the multi-LLM discussion.
It uses a deterministic proxy that queries multiple LLMs (defined in a config JSON)
and iteratively gathers responses until convergence or a maximum number of interactions is reached.
"""

import json
import os
import sys
from datetime import datetime
import time
import click
import re

from peer_consensus.llm_providers import get_gpt_implementation
from peer_consensus.utils.logging import get_logger
from peer_consensus.utils.db_manager import DBManager
from peer_consensus.utils.convergence import check_convergence

logger = get_logger(__name__)

def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return json.load(f)

def build_initial_prompt(model_name: str, total_models: int, research_prompt: str, convergence_phrase: str) -> list:
    """
    Build the initial prompt for a model.
    The prompt instructs the model to provide a substantive, evidence-based opinion on cancer treatment,
    focusing solely on the topic and current scientific evidence.
    It must include exactly the following sentence somewhere in the response:
      'I am in agreement with {percentage}% of the overall opinions given by my peers.'
    """
    prompt_text = (
        f"Please provide a substantive, evidence-based opinion on {research_prompt}. "
        "Your answer should be direct and grounded in current scientific research, focusing solely on the topic. "
        f"Additionally, include exactly the following sentence somewhere in your response: '{convergence_phrase}'. "
        "Do not include any role-play, meta commentary, or discussion of your own identity as an AI."
    )
    return [{"role": "user", "content": prompt_text}]

def build_iterative_prompt(model_name: str, own_last_response: str, peer_responses: dict, convergence_phrase: str) -> list:
    """
    Build an iterative prompt for a model.
    The prompt instructs the model to update its evidence-based opinion on cancer treatment,
    based on its previous answer and the latest opinions from its peers.
    It must include exactly the following sentence somewhere in the response:
      'I am in agreement with {percentage}% of the overall opinions given by my peers.'
    The response should remain factual and focused on current scientific evidence without role-playing.
    """
    prompt_text = (
        f"Based on your previous response (shown below) and the latest opinions from your peers, "
        "please update your evidence-based opinion on a promising avenue for cancer treatment. "
        "Ensure that your answer is factual, grounded in current scientific research, and focused solely on the topic. "
        f"Include exactly the following sentence somewhere in your response: '{convergence_phrase}'.\n\n"
        f"Your previous answer:\n{own_last_response}\n\n"
        "Your peers' latest opinions:\n"
    )
    for peer, response in peer_responses.items():
        prompt_text += f"{peer}: {response}\n"
    return [{"role": "user", "content": prompt_text}]

def extract_convergence(response: str) -> float:
    """
    Extracts the convergence percentage from the response text.
    Expects a line exactly: 
    "I am in agreement with {number}% of the overall opinions given by my peers."
    """
    match = re.search(r"I am in agreement with (\d+(?:\.\d+)?)% of the overall opinions given by my peers\.", response)
    if match:
        return float(match.group(1))
    return 0.0

@click.command()
@click.option("--config", required=True, type=click.Path(exists=True), help="Path to configuration JSON file.")
@click.option("--prompt-title", required=True, help="Title for the discussion session.")
@click.option("--max-interactions", required=True, type=int, help="Maximum number of interactions (>= 2).")
@click.option("--research-prompt", required=True, help="Research prompt (e.g., 'a promising avenue for cancer treatment').")
def run_discussion(config, prompt_title, max_interactions, research_prompt):
    if max_interactions < 2:
        click.echo("Error: max-interactions must be at least 2.")
        sys.exit(1)

    config_data = load_config(config)
    responses_folder_path = config_data.get("responses_folder_path", "responses")
    convergence_threshold = config_data.get("convergenceThreshold", 90)  # default to 90%

    models_config = config_data.get("models", [])
    total_models = len(models_config)
    if total_models == 0:
        click.echo("Error: No models found in config.")
        sys.exit(1)

    # Initialize LLM instances; ensure each model's provider has an implementation.
    gpt_models = {}
    for model_cfg in models_config:
        provider = model_cfg.get("model_provider")
        try:
            instance = get_gpt_implementation(
                api_key=model_cfg["api_key"],
                model_name=model_cfg["version"],
                model_provider=provider
            )
            gpt_models[model_cfg["name"]] = instance
        except Exception as e:
            click.echo(f"Error initializing model {model_cfg.get('name')}: {e}")
            sys.exit(1)

    # Create output session folder: responses_folder_path/{prompt_title} - {timestamp}
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    session_folder = os.path.join(responses_folder_path, f"{prompt_title} - {timestamp}")
    os.makedirs(session_folder, exist_ok=True)

    # Initialize a SQLite DB for each model using DBManager.
    db_managers = {}
    for model_name in gpt_models.keys():
        db_path = os.path.join(session_folder, f"{model_name}.db")
        db_managers[model_name] = DBManager(db_path)
        db_managers[model_name].initialize_table()

    # Define the required convergence phrase that each model must include.
    required_convergence_phrase = "I am in agreement with {percentage}% of the overall opinions given by my peers."

    latest_responses = {}  # Store the latest response from each model.
    
    click.echo(f"Starting discussion with {total_models} models. Max interactions: {max_interactions}")
    click.echo(f"Session folder: {session_folder}")
    
    # Interaction loop.
    for interaction in range(1, max_interactions + 1):
        click.echo(f"\n--- Interaction {interaction} ---")
        for model_name, gpt_instance in gpt_models.items():
            if interaction == 1:
                messages = build_initial_prompt(model_name, total_models, research_prompt, required_convergence_phrase)
            else:
                own_last = latest_responses.get(model_name, "")
                # Prepare peer responses: exclude the current model.
                peer_responses = {name: resp for name, resp in latest_responses.items() if name != model_name}
                messages = build_iterative_prompt(model_name, own_last, peer_responses, required_convergence_phrase)
            
            click.echo(f"Querying model {model_name}...")
            response_text = gpt_instance.generate_completion(messages)
            click.echo(f"Response from {model_name}:\n{response_text}\n")
            convergence_val = extract_convergence(response_text)
            
            # Save response in corresponding DB.
            db_managers[model_name].insert_response(interaction, response_text, convergence_val)
            latest_responses[model_name] = response_text
        
        # Check overall convergence across models.
        converged, avg_convergence = check_convergence(latest_responses, convergence_threshold)
        click.echo(f"Average convergence after interaction {interaction}: {avg_convergence}%")
        if converged:
            click.echo("Consensus achieved. Stopping discussion.")
            break

    click.echo("Discussion complete.")
    click.echo(f"Run the following command to review the conversation:")
    click.echo(f'poetry run review-opinions --session-folder "{session_folder}" --port 5000')

if __name__ == "__main__":
    run_discussion()

