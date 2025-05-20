from typing import List, cast

import chainlit as cl
import yaml

import pandas as pd
import json

# To connect to Azure SQL Database
import os
from dotenv import load_dotenv
load_dotenv(override=True)

import pyodbc, struct
from azure import identity

# For Autogen Agents
from autogen_ext.models.azure import AzureAIChatCompletionClient
from azure.core.credentials import AzureKeyCredential
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import TextMentionTermination, SourceMatchTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import ModelClientStreamingChunkEvent, TextMessage
from autogen_core.models import UserMessage
from autogen_core import CancellationToken

from system_messages import QueryExtractorAgentMessage, ReportFinderAgentMessage, SQLGeneratorAgentMessage, ReviewerAgentMessage, EmailDraftAgentMessage
from agents_chainlit import QueryExecutionAgent

async def user_input_func(prompt: str, cancellation_token: CancellationToken | None = None) -> str:
    """Get user input from the UI for the user proxy agent."""
    try:
        response = await cl.AskUserMessage(content=prompt).send()
    except TimeoutError:
        return "User did not provide any input within the time limit."
    if response:
        return response["output"]  # type: ignore
    else:
        return "User did not provide any input."


async def user_action_func(prompt: str, cancellation_token: CancellationToken | None = None) -> str:
    """Get user action from the UI for the user proxy agent."""
    try:
        response = await cl.AskActionMessage(
            content="Pick an action",
            actions=[
                cl.Action(name="approve", label="Approve", payload={"value": "approve"}),
                cl.Action(name="reject", label="Reject", payload={"value": "reject"}),
            ],
        ).send()
    except TimeoutError:
        return "User did not provide any input within the time limit."
    if response and response.get("payload"):  # type: ignore
        if response.get("payload").get("value") == "approve":  # type: ignore
            return "APPROVE."  # This is the termination condition.
        else:
            return "REJECT."
    else:
        return "User did not provide any input."

@cl.on_chat_start  # type: ignore
async def start_chat() -> None:
    FOUNDRY_KEY = os.environ.get('FOUNDRY_KEY')

    model_client = AzureAIChatCompletionClient(
        model="gpt-4o-mini",
        endpoint="https://msfthackathong9909733395.services.ai.azure.com/models",
        # endpoint="https://msfthackathong9909733395.openai.azure.com/",
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
    # Create a stream.
    # stream = model_client.create_stream([UserMessage(content="Write a poem about the ocean", source="user")])
    # async for chunk in stream:
    #     print(chunk, end="", flush=True)
    # print()

    # Close the client.
    # await model_client.close()

    QueryExtractorAgent = AssistantAgent(
        name="QueryExtractorAgent",
        model_client=model_client,
        system_message=QueryExtractorAgentMessage,
        model_client_stream=True,  # Enable model client streaming.
    )

    ReportFinderAgent = AssistantAgent(
        name="ReportFinderAgent",
        model_client=model_client,
        system_message=ReportFinderAgentMessage,
        model_client_stream=True,  # Enable model client streaming.
    )

    SQLGeneratorAgent = AssistantAgent(
        name="SQLGeneratorAgent",
        model_client=model_client,
        system_message=SQLGeneratorAgentMessage,
        model_client_stream=True,
    )
    QueryExecutionAgentInstance = QueryExecutionAgent(
        name="QueryExecutionAgent",
        model_client_stream=True,
    )

    ReviewerAgent = AssistantAgent(
        name="ReviewerAgent",
        model_client=model_client,
        system_message="You are a critic. Provide one short sentence of constructive feedback. "
        "Respond with 'APPROVE' if your feedback has been addressed.",
        model_client_stream = True
    )

    # Create the user proxy agent.
    UserReportSelector = UserProxyAgent(
        name="UserReportSelector",
        # input_func=user_input_func, # Uncomment this line to use user input as text.
        input_func=user_action_func,  # Uncomment this line to use user input as action.
    )

    # Create the user proxy agent.
    UserFinalReview = UserProxyAgent(
        name="UserFinalReview",
        # input_func=user_input_func, # Uncomment this line to use user input as text.
        input_func=user_action_func,  # Uncomment this line to use user input as action.
    )
    
    # Create the email generator agent.
    # EmailDraftGenerator = EmailDraftGeneratorAgent(
    #     name="EmailDraftGenerator",
    #     model_client=model_client,
    #     system_message=EmailDraftAgentMessage,
    #     model_client_stream=True
    # )
    EmailDraftGenerator = AssistantAgent(
        name="EmailDraftGeneratorAgent",
        model_client=model_client,
        system_message=EmailDraftAgentMessage,
        model_client_stream=True,  # Enable model client streaming.
    )

    # Termination condition.
    # termination = TextMentionTermination("APPROVE", sources=["UserFinalReview"])
    termination = SourceMatchTermination(sources=["EmailDraftGeneratorAgent"])

    # Chain the assistant, critic and user agents using RoundRobinGroupChat.
    group_chat = RoundRobinGroupChat([
        QueryExtractorAgent,
        # ReportFinderAgent,
        # UserReportSelector,
        SQLGeneratorAgent,
        QueryExecutionAgentInstance,
        ReviewerAgent,
        UserFinalReview,
        EmailDraftGenerator
        ], termination_condition=termination)

    # Set the assistant agent in the user session.
    cl.user_session.set("prompt_history", "")  # type: ignore
    cl.user_session.set("team", group_chat)  # type: ignore


@cl.set_starters  # type: ignore
async def set_starts() -> List[cl.Starter]:
    return [
        cl.Starter(
            label="Claim Amounts by Category",
            message="From: Microsoft (client_code=2) Can you show me claims amounts broken down by the broadest category?",
        ),
        cl.Starter(
            label="Drug Claims: Brand vs Generic?",
            message="From: IBM (client_code = 1) How many of the drug claims paid are Brand vs Generic?",
        ),
        cl.Starter(
            label="Claimed Dental Codes",
            message="From: IBM (client_code = 1) What types of dental codes (and their descriptions) were claimed on my plan? Please aggregate them.",
        ),
    ]


@cl.on_message  # type: ignore
async def chat(message: cl.Message) -> None:
    # Get the team from the user session.
    team = cast(RoundRobinGroupChat, cl.user_session.get("team"))  # type: ignore
    # Streaming response message.
    streaming_response: cl.Message | None = None
    # Stream the messages from the team.
    async for msg in team.run_stream(
        task=[TextMessage(content=message.content, source="user")],
        cancellation_token=CancellationToken(),
    ):
        if isinstance(msg, ModelClientStreamingChunkEvent):
            # Stream the model client response to the user.
            if streaming_response is None:
                # Start a new streaming response.
                streaming_response = cl.Message(content="", author=msg.source)
            await streaming_response.stream_token(msg.content)
        # elif isinstance(msg, TableStreamingChunkEvent):
        #     # Stream the table response to the user.
        #     if streaming_response is None:
        #         # Start a new streaming response.
        #         streaming_response = cl.Message(content="", author=msg.source)
        #     await streaming_response.stream_token(msg.content)
        elif streaming_response is not None:
            # Done streaming the model client response.
            # We can skip the current message as it is just the complete message
            # of the streaming response.
            await streaming_response.send()
            # Reset the streaming response so we won't enter this block again
            # until the next streaming response is complete.
            streaming_response = None
        elif isinstance(msg, TaskResult):
            # Send the task termination message.
            final_message = "Thanks for chatting! You can send me a new question if you'd like."
            # if msg.stop_reason:
                # final_message += msg.stop_reason
            await cl.Message(content=final_message).send()
        else:
            # Skip all other message types.
            pass