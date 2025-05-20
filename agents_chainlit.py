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

from typing import AsyncGenerator, List, Sequence
from dataclasses import dataclass

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, UserMessage, TextMessage, ModelClientStreamingChunkEvent
from autogen_core.model_context import UnboundedChatCompletionContext
from autogen_core import CancellationToken

@dataclass
class QueryResultMessage(BaseChatMessage):
    """A pandas DataFrame JSON Message"""
    content: str
    type: str
    
class QueryExecutionAgent(BaseChatAgent):
    def __init__(self, name: str, model_client_stream: bool):
        super().__init__(name, description="A SQL Query Execution agent.")
        self.model_client_stream = model_client_stream
        # self.query = query

    @property
    def produced_message_types(self) -> Sequence[type[QueryResultMessage]]:
        return (QueryResultMessage,)
    
    def get_conn(self, connection_string):
        conn = pyodbc.connect(connection_string)
        return conn
    
    async def on_messages(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken) -> Response:
        # Calls the on_messages_stream.
        response: Response | None = None
        async for message in self.on_messages_stream(messages, cancellation_token):
            if isinstance(message, Response):
                response = message
        assert response is not None
        return response
    
    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        inner_messages: List[BaseAgentEvent | BaseChatMessage] = []
        connection_string = os.environ['AZURE_SQL_CONNECTIONSTRING']
        
        # response: Response | None = None
        print("-"*80, f"\nMESSAGES ARE: \n{messages}\n\n")
        
        # extracts the SQL portion of the message 
        query = messages[-1].content.split('```sql')[-1].split('```')[0]
        # print("-"*80, f"\nTHE SQL QUERY IS: \n{query}\n\n")
        rows = []
        with self.get_conn(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                rows.append(row)
        df = pd.DataFrame((tuple(t) for t in rows), columns=columns)
        assert isinstance(df, pd.DataFrame)
        response = TextMessage(content=df.to_json(), source=self.name)

        if self.model_client_stream:
            yield ModelClientStreamingChunkEvent(
                content=df.to_markdown(index=False),
                source=self.name, type='ModelClientStreamingChunkEvent')

        yield Response(chat_message=response)

        # {'message': ModelClientStreamingChunkEvent(source='SQLGeneratorAgent', models_usage=None, metadata={}, content=' the', type='ModelClientStreamingChunkEvent')}
    
        # for i in range(self._count, 0, -1):
        #     msg = TextMessage(content=f"{i}...", source=self.name)
        #     inner_messages.append(msg)
        #     yield msg
        # The response is returned at the end of the stream.
        # It contains the final message and all the inner messages.
        # yield Response(chat_message=TextMessage(content="Done!", source=self.name), inner_messages=inner_messages)


    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass
