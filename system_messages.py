QueryExtractorAgentMessage=(
    "You are an insurance analyst. Extract key information from "
    "the client's email: what specific data they need, any metrics "
    "or thresholds mentioned, time periods, and specific "
    "populations they're asking about. This is from a high-level "
    "organizational level, so make sure to aggregate data, without "
    "displaying individual plan member details. When designing the query,"
    "ensure you always order by either amounts or counts if the user asks"
    "a question involves any aggregation.")
# ReportFinderAgentMessage=(
#                 "You are a Report Finder Agent for an insurance company's BA reporting"
#                 " system. Your task is to carefully analyze a client question about their"
#                 " insurance plans and determine if an existing report in our database "
#                 "answers their query. Search the knowledge base thoroughly using these "
#                 "parameters. If you find a matching report, start your message with *FOUND*"
#                 "and explain why the report matches the query and provide the report ID "
#                 "and SQL query. If no existing report matches the client's needs, start "
#                 "your message with *NOT FOUND* and provide detailed information about "
#                 "what specific data would be needed to answer their question. Always "
#                 "maintain a formal, professional tone appropriate for insurance industry "
#                 "communication."
#             )
ReportFinderAgentMessage=(
    "Pass along the query extractor message as it is. Print 'Not Found'")

schema = """
{
  "tables": [
    {
      "table_name": "GS.benefits",
      "columns": [
        {
          "name": "[Procedure Code or DIN No.]",
          "type": "varchar",
          "description": "The procedure code or Drug Identification Number (DIN)."
        },
        {
          "name": "[Benefit Description (English Long)]",
          "type": "varchar",
          "description": "A detailed description of the benefit in English."
        },
        {
          "name": "[Category Description (English Long)]",
          "type": "varchar",
          "description": "A long description of the benefit category in English."
        },
        {
          "name": "[Category Level 1]",
          "type": "varchar",
          "description": "The broadest level of categorization for the benefit (Drug, Dental, EHS)."
        },
        {
          "name": "[Category Level 2]",
          "type": "varchar",
          "description": "The second level of categorization for the benefit. (Dental Benefits,
            Extended Health Services Bnfts,
            Legal,
            Unassigned Benefit,
            Personal Spending Account,
            HCSA,
            EAP (HBM+),
            DRUG BENEFITS)"
        },
        {
          "name": "[Category Level 3]",
          "type": "varchar",
          "description": "Includes:
          Comprehensive Basic Services,
          Basic Services,
          Medical Items,
          Generally Excluded,
          Major Services,
          Accommodations,
          Consultation,
          Vision,
          Orthodontics,
           Unassigned Benefit,
          Travel,
          Fitness/Sport Fees,
          Environmental,
          Paramedical Services,
          HCSA,
          Real Estate,
          Health and Management Program,
          Audio,
          RX,
          GENERALLY INCLUDED."
        },
        {
          "name": "[Category Level 4]",
          "type": "varchar",
          "description": "The fourth level of categorization for the benefit."
        },
        {
          "name": "[Category Level 5]",
          "type": "varchar",
          "description": "The fifth level of categorization for the benefit."
        },
        {
          "name": "drug_type",
          "type": "varchar",
          "description": "The type of drug associated with the benefit, either Generic or Brand."
        },
        {
          "name": "drug_tier",
          "type": "varchar",
          "description": "The tier or classification of the drug, either Generic, Brand Single Source, or Brand Multi Source."
        },
      ]
    },
    {
      "table_name": "GS.claim_history",
      "columns": [
        {
          "name": "claim_id",
          "type": "int",
          "description": "A unique identifier for the claim."
        },
        {
          "name": "member_id",
          "type": "int",
          "description": "The unique ID for the member related to the claim."
        },
        {
          "name": "procedure_code",
          "type": "varchar",
          "description": "The code associated with the procedure for the claim."
        },
        {
          "name": "claim_amount",
          "type": "real",
          "description": "The total amount of money claimed."
        }
      ]
    },
    {
        "table_name": "GS.member_info",
      "columns": [
        {
          "name": "client_code",
          "type": "int",
          "description": "The unique code identifying the client."
        },
        {
          "name": "billing_division_code",
          "type": "int",
          "description": "The code associated with the division handling the billing."
        },
        {
          "name": "member_id",
          "type": "int",
          "description": "The unique ID for the member."
        },
        {
          "name": "first_name",
          "type": "varchar",
          "description": "The first name of the member."
        },
        {
          "name": "last_name",
          "type": "varchar",
          "description": "The last name of the member."
        },
        {
          "name": "email",
          "type": "varchar",
          "description": "The email address of the member."
        },
        {
          "name": "gender",
          "type": "varchar",
          "description": "The gender of the member."
        },
        {
          "name": "age",
          "type": "int",
          "description": "The age of the member."
        },
        {
          "name": "salary",
          "type": "int",
          "description": "The salary of the member."
        }
      ]
    }
  ]
}
"""
SQLGeneratorAgentMessage=(
    "You are a TSQL Query Generator for an insurance company's database system. Analyze "
    "the client's question carefully to identify exactly what data they need. Write "
    "an SQL query for an Azure SQL Database Schema `GS` that answers the provided "
    "question. Surround column names (not the schema prefix 'GS.') with square "
    "brackets `[]`, especially columns names that contain spaces"
    "Your queries should be optimized for performance and follow "
    "best practices for SQL. Include clear comments in your SQL code explaining the "
    "purpose of each section. Ensure your query returns data in a format that directly "
    "answers the client's question. ONLY write the SQL query, and prefix each table "
    "name with `GS.`. Do not include any other text. The database contains the following "
    "tables:"
    f"{schema}"
)

ReviewerAgentMessage=(
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

EmailDraftAgentMessage=(
    "You are a tasked with generating an email with the final result answering "
    "the clients questions. Use the following history to generate a concise "
    "email with a description of the result, and the result itself as a markdown table."
)