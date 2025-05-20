from dataclasses import dataclass
import pandas as pd

@dataclass
class Message:
    content: str

@dataclass
class GenerateInstructionMessage:
    content: str
    feedback: str

@dataclass
class SQLQueryMessage:
    question: str
    query: str

@dataclass
class ReviewMessage:
    question: str
    query: str
    table: list