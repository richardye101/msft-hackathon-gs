import asyncio
import argparse
from autogen_core import (
    SingleThreadedAgentRuntime,
    TopicId,
)
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from autogen_ext.models.azure import AzureAIChatCompletionClient
from azure.core.credentials import AzureKeyCredential

import pandas as pd
import os
from message_classes import Message
from agents import QueryExtractorAgent, ReportFinderAgent, SQLGeneratorAgent, QueryExecutionAgent, ReviewerAgent, EmailDraftAgent

query_extractor_topic_type = "QueryExtractorAgent"
report_finder_topic_type = "ReportFinderAgent"
sql_generator_topic_type = "SQLGeneratorAgent"
query_execution_topic_type = "QueryExecutionAgent"
ready_for_review_topic_type = "ReviewerAgent"
result_topic_type = "EmailDraftAgent"

async def setup_agents():
    FOUNDRY_KEY = os.environ.get('FOUNDRY_KEY')
    model_client = AzureAIChatCompletionClient(
        model="gpt-4o-mini",
        endpoint="https://msfthackathong9909733395.services.ai.azure.com/models",
        # Created an AI Foundry Hub, then a project within it, then a model. 
        # Can find and access the inference endpoint and Key within the Project -> My assets -> Models + endpoints
        credential=AzureKeyCredential(FOUNDRY_KEY),
        model_info={
            "json_output": False,
            "function_calling": False,
            "vision": False,
            "family": "unknown",
            "structured_output":False,
        },
    )

    # result = await model_client.create([UserMessage(content="What is the capital of France?", source="user")])
    # print(result)

    runtime = SingleThreadedAgentRuntime()

    await QueryExtractorAgent.register(
        runtime, type=query_extractor_topic_type, factory=lambda: QueryExtractorAgent(model_client=model_client)
    )

    await ReportFinderAgent.register(runtime, type=report_finder_topic_type, factory=lambda: ReportFinderAgent(model_client=model_client))

    await SQLGeneratorAgent.register(
        runtime, type=sql_generator_topic_type, factory=lambda:SQLGeneratorAgent(model_client=model_client)
    )

    await QueryExecutionAgent.register(
        runtime, type=query_execution_topic_type, factory=lambda:QueryExecutionAgent(model_client=model_client)
    )

    await ReviewerAgent.register(
        runtime, type=ready_for_review_topic_type, factory=lambda:ReviewerAgent(model_client=model_client)
    )

    await EmailDraftAgent.register(runtime, type=result_topic_type, factory=lambda: EmailDraftAgent())

    return (runtime, model_client)

async def run(query):
    runtime, model_client = await setup_agents()
    runtime.start()

    await runtime.publish_message(
        Message(content=query),
        topic_id=TopicId(query_extractor_topic_type, source="default"),
    )

    await runtime.stop_when_idle()
    await model_client.close()

def main():
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description="This script accepts an input query from the terminal.")

    # Define the arguments the script expects
    parser.add_argument('query', type=str, help='What would you like to answer?')
    # parser.add_argument('age', type=int, help='Your age')
    # (
    #         "From: IBM (client_code = 1)"
    #         "How many of the drug claims paid are Brand vs Generic?"
    #     )
    # Parse the arguments from the command line
    args = parser.parse_args()

    # Access the arguments
    # print(f"Hello, {args.name}! You are {args.age} years old.")
    asyncio.run(run(args.query))

if __name__ == '__main__':
    main()