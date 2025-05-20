# Microsoft Hackathon: GreenShield Sales Support Agent

This is a Multi-Agent PoC for a Sales Support use case. 

## Current Process:
Customer service representatives (CSR) would enter questions received from clients regarding the client insurance plan usage. They would have to go into SAP Business Objects to find the relevant and correct report to generate the data to answer the client request. This process is time-consuming as the CSR would have to know the report from memeory, or manually find it in a list of hundreds of reports. The response to the client carries a 3-day turnaround time, however if no report exists, the request is escalated and will require a 10-day turnaround time.

## Proposed solution:
Using Agentic AI to breakdown the client request, and find the correct report using semantic embeddings of the report SQL converted to plain text. As a fallback in the case a relevant existing report is not found, the solution will create a SQL query based on the database and table schema to pull the correct information. 

## Current state:
This PoC is currently an implementation of the fallback, using a mocked database living in Azure SQL. There is also a human-in-the-loop element after the SQL query is run against the database, to verify the correct information was retrieved.

To do this, we create 4 agents.
1. To parse and understand the client request.
2. To generate the equivalent SQL query of the client request
3. To run the generated SQL query against the Azure SQL database
4. To generate an email summary of the response, and data.

## To run this code
```
pip install -r requirements.txt
chainlit run app_chainlit.py -h
```
