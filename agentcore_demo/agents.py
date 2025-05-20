# To connect to Azure SQL Database
import os
from dotenv import load_dotenv
load_dotenv(override=True)

import pyodbc, struct
from azure import identity

from typing import Union
from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import json

# For Autogen Agents
from autogen_core import (
    MessageContext,
    RoutedAgent,
    TopicId,
    message_handler,
    type_subscription,
)
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from message_classes import Message, GenerateInstructionMessage, SQLQueryMessage, ReviewMessage

query_extractor_topic_type = "QueryExtractorAgent"
report_finder_topic_type = "ReportFinderAgent"
sql_generator_topic_type = "SQLGeneratorAgent"
query_execution_topic_type = "QueryExecutionAgent"
ready_for_review_topic_type = "ReviewerAgent"
result_topic_type = "EmailDraftAgent"

@type_subscription(topic_type=query_extractor_topic_type)
class QueryExtractorAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("A query extractor agent.")

        # TO-DO: NEED TO REPLACE THIS SYSTEM MESSAGE
        self._system_message = SystemMessage(
            content=(
                "You are an insurance analyst Extract key information from the client's email: what specific data they need, any metrics or thresholds mentioned, time periods, and specific populations they're asking about."
            )
        )
        self._model_client = model_client

    @message_handler
    async def handle_user_request(self, message: Message, ctx: MessageContext) -> None:
        prompt = f"Request: {message.content}"
        llm_result = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt, source=self.id.key)],
            cancellation_token=ctx.cancellation_token,
        )
        response = llm_result.content
        assert isinstance(response, str)
        print(f"{'-'*80}\n{self.id.type}:\n{response}")

        await self.publish_message(Message(response), topic_id=TopicId(report_finder_topic_type, source=self.id.key))

@type_subscription(topic_type=report_finder_topic_type)
class ReportFinderAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("A report finder agent.")
        self._system_message = SystemMessage(
            content=(
                "You are a Report Finder Agent for an insurance company's BA reporting"
                " system. Your task is to carefully analyze a client question about their"
                " insurance plans and determine if an existing report in our database "
                "answers their query. Search the knowledge base thoroughly using these "
                "parameters. If you find a matching report, start your message with *FOUND*"
                "and explain why the report matches the query and provide the report ID "
                "and SQL query. If no existing report matches the client's needs, start "
                "your message with *NOT FOUND* and provide detailed information about "
                "what specific data would be needed to answer their question. Always "
                "maintain a formal, professional tone appropriate for insurance industry "
                "communication."
            )
        )
        self._model_client = model_client

    @message_handler
    async def handle_question(self, message: Message, ctx: MessageContext) -> None:
        prompt = f"Below is the question to answer:\n\n{message.content}"

        # To Do: Implement a RAG agent to search existing reports

        llm_result = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt, source=self.id.key)],
            cancellation_token=ctx.cancellation_token,
        )
        # response = llm_result.content
        response = ""
        assert isinstance(response, str)
        print(f"{'-'*80}\n{self.id.type}:\n{response}")

        # To Do: send message to either report generator agent
        if response.startswith("*FOUND*"):
            await self.publish_message(Message(response), topic_id=TopicId(query_execution_topic_type, source=self.id.key))
        else:
            await self.publish_message(
                GenerateInstructionMessage(message.content, feedback=""),
                topic_id=TopicId(sql_generator_topic_type, source=self.id.key))
            
@type_subscription(topic_type=sql_generator_topic_type)
class SQLGeneratorAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("A SQL Query Generator agent.")
        self.schema = """
{
  "tables": [
    {
      "table_name": "GS.benefits",
      "columns": [
        {"column_name": "procedure_code", "data_type": "varchar"},
        {"column_name": "benefit_desc", "data_type": "varchar"},
        {"column_name": "maximum_claim_amt", "data_type": "int"},
        {"column_name": "salary_class", "data_type": "int"},
        {"column_name": "drug_type", "data_type": "varchar"},
        {"column_name": "drug_tier", "data_type": "varchar"}
      ]
    },
    {
      "table_name": "GS.claim_history",
      "columns": [
        {"column_name": "claim_id", "data_type": "int"},
        {"column_name": "member_id", "data_type": "int"},
        {"column_name": "procedure_code", "data_type": "varchar"},
        {"column_name": "claim_amount", "data_type": "real"},
        {"column_name": "diagnosis_code", "data_type": "varchar"},
        {"column_name": "claim_date", "data_type": "datetime"}
      ]
    },
    {
      "table_name": "GS.disease_procedure_map",
      "columns": [
        {"column_name": "diagnosis_code", "data_type": "varchar"},
        {"column_name": "diagnosis_description", "data_type": "varchar"},
        {"column_name": "procedure_code", "data_type": "varchar"},
        {"column_name": "benefit_desc", "data_type": "varchar"}
      ]
    },
    {
      "table_name": "GS.member_info",
      "columns": [
        {"column_name": "client_code", "data_type": "int"},
        {"column_name": "billing_division_code", "data_type": "int"},
        {"column_name": "member_id", "data_type": "int"},
        {"column_name": "first_name", "data_type": "varchar"},
        {"column_name": "last_name", "data_type": "varchar"},
        {"column_name": "email", "data_type": "varchar"},
        {"column_name": "gender", "data_type": "varchar"},
        {"column_name": "age", "data_type": "int"},
        {"column_name": "salary", "data_type": "int"}
      ]
    }
  ]
}
"""
        self._system_message = SystemMessage(
            content=(
                "You are a SQL Query Generator for an insurance company's database system. Analyze "
                "the client's question carefully to identify exactly what data they need. Write "
                "a SQL query for an Azure SQL Database Schema `GS` that answers the provided "
                "question. Always include appropriate WHERE clauses to limit results based on "
                "the specific parameters in the client's question (date ranges, dollar amounts, "
                "plan types, etc.). Your queries should be optimized for performance and follow "
                "best practices for SQL. Include clear comments in your SQL code explaining the "
                "purpose of each section. Ensure your query returns data in a format that directly "
                "answers the client's question. ONLY write the SQL query, and prefix each table "
                "name with `GS.`. Do not include any other text. The database contains the following "
                "tables:"
                f"{self.schema}"
            )
        )
        self._model_client = model_client

    @message_handler
    async def handle_question(self, message: GenerateInstructionMessage, ctx: MessageContext) -> None:
        prompt = f"Question to convert to SQL Query:\n{message.content}."
        print(f"Entered prompt for Query generation: {prompt}")
        if message.feedback:
            prompt += f"Using this feedback:\n{message.feedback}"
        llm_result = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt, source=self.id.key)],
            cancellation_token=ctx.cancellation_token,
        )
        response = llm_result.content
        assert isinstance(response, str)
        print(f"{'-'*80}\n{self.id.type}:\n{response}")
        question_and_query = SQLQueryMessage(question=message.content, query=response)
        await self.publish_message(question_and_query, topic_id=TopicId(query_execution_topic_type, source=self.id.key))

@type_subscription(topic_type=query_execution_topic_type)
class QueryExecutionAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("A SQL Query Execution agent.")
    
    @message_handler
    async def handle_sql_query(self, message: SQLQueryMessage, ctx: MessageContext) -> None:
        connection_string = os.environ['AZURE_SQL_CONNECTIONSTRING']
        
        # extracts the SQL portion of the message 
        query = message.query.split('```sql')[-1].split('```')[0]
        rows = []
        with self.get_conn(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                rows.append(row)
        response = pd.DataFrame((tuple(t) for t in rows), columns=columns)
        assert isinstance(response, pd.DataFrame)

        print(f"{'-'*80}\n{self.id.type}:\n{response}")
        # TO-DO: Write code to run the query against the database
        response_for_review = ReviewMessage(
            question=message.question,
            query=message.query,
            table=response.to_json()
        )
        await self.publish_message(response_for_review, topic_id=TopicId(ready_for_review_topic_type, source=self.id.key))
    
    def get_conn(self, connection_string):
        conn = pyodbc.connect(connection_string)
        return conn
    
@type_subscription(topic_type=ready_for_review_topic_type)
class ReviewerAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("A Result Reviewer agent.")
        self._system_message = SystemMessage(
            content=(
                "You are a reviewer agent tasked with comparing a question, "
                "the corresponding SQL query, and the head of the result " 
                "table to ensure that the original question is answered correctly."
                "You are a Reviewer Agent responsible for quality control in an "
                "insurance reporting system. Your critical role is to verify that "
                "the the corresponding SQL query, and the head of the result " 
                "table truly answers the client's original question. Then carefully "
                "examine the resulting tables provided to you. Verify that: "
                "1) All requested information is present and complete; "
                "2) The data directly addresses the specific parameters mentioned by "
                "the client (time periods, dollar amounts, specific populations); "
                "3) The format is clear and professional; "
                "4) No extraneous or confusing information is included. If the report "
                "fully satisfies the client's query, approve it by ONLY responding "
                "with **APPROVED**. If any information is missing or inappropriate, "
                "clearly articulate what needs to be corrected under a **FEEDBACK** heading. "
                "Use your insurance industry expertise to ensure the information would "
                "be valuable and understandable to the client."
            )
        )
        self._model_client = model_client

    @message_handler
    async def handle_result(self, message: ReviewMessage, ctx: MessageContext) -> None:
        prompt = (f"Review the following question:\n{message.question}."
                  f"SQL Query:\n{message.query}"
                  f"Result:\n {pd.DataFrame(eval(message.table))}"
                )
        llm_result = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt, source=self.id.key)],
            cancellation_token=ctx.cancellation_token,
        )
        response = llm_result.content
        assert isinstance(response, str)
        print(f"{'-'*80}\n{self.id.type}:\n{response}")
        # TO-DO: Write code to run the query against the database
        if response.startswith("**APPROVED**"):
            await self.publish_message(message, topic_id=TopicId(result_topic_type, source=self.id.key))
        else:
            await self.publish_message(
                GenerateInstructionMessage(message.question, feedback=response),
                topic_id=TopicId(result_topic_type, source=self.id.key))
            
@type_subscription(topic_type=result_topic_type)
class EmailDraftAgent(RoutedAgent):
    def __init__(self) -> None:
        super().__init__("A user agent that outputs the final answer to the user.")

    @message_handler
    async def handle_final_copy(self, message: ReviewMessage, ctx: MessageContext) -> None:
        print(f"\n{'-'*80}\n{self.id.type} Creating an email draft...")
        print(f"Question: {message.question}\n Query: {message.query}\n Result: {pd.DataFrame(eval(message.table))}")
        # To Do: Write code to handle putting the resulting table into a XLSX, 
        # and sending it to an email client as a draft.