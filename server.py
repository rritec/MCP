import os
import sys
import struct
import logging
import requests as req
import pandas as pd
import pyodbc
from mcp.server.fastmcp import FastMCP
from azure.identity import InteractiveBrowserCredential

# Safe logging for stdio - never use print()
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

mcp = FastMCP("fabric-sql-agent")

# ── CONFIG — update these two values ────────────────────────
SQL_ENDPOINT = "3lreftske4pednomh3rwhipz6u-z2k7iexoniyulgfvvljiq3ucuu.datawarehouse.fabric.microsoft.com"
DATABASE = "bronze"
# ────────────────────────────────────────────────────────────

SCHEMA_CONTEXT = """
Tables available in Fabric Lakehouse (bronze):

dbo.emp columns:
  empno    INT       - Employee number (primary key)
  ename    VARCHAR   - Employee name
  job      VARCHAR   - Job title: CLERK, MANAGER, ANALYST, SALESMAN, PRESIDENT, CFO
  mgr      INT       - Manager employee number (0 if no manager)
  hiredate DATETIME  - Date hired
  sal      FLOAT     - Salary
  comm     FLOAT     - Commission (0 if none)
  deptno   INT       - Department number (foreign key)

dbo.dept columns:
  deptno   INT       - Department number (primary key)
  dname    VARCHAR   - Department name: ACCOUNTING, RESEARCH, SALES, OPERATIONS
  loc      VARCHAR   - Location city

Relationship: emp.deptno = dept.deptno
"""


def get_connection():
    """Creates an authenticated connection to Fabric SQL Endpoint using browser login."""
    credential = InteractiveBrowserCredential()
    token = credential.get_token("https://database.windows.net/.default")

    # Pack the token into the format pyodbc expects
    token_bytes = token.token.encode("UTF-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={SQL_ENDPOINT},1433;"
        f"Database={DATABASE};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
    )

    SQL_COPT_SS_ACCESS_TOKEN = 1256
    conn = pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    return conn


@mcp.tool()
def list_tables() -> str:
    """
    Lists all available tables in the Fabric Lakehouse.
    Use this first to understand what data is available.
    """
    try:
        conn = get_connection()
        query = """
            SELECT TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = 'dbo'
            ORDER BY TABLE_NAME
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return f"Available tables in '{DATABASE}':\n\n{df.to_string(index=False)}"
    except Exception as e:
        logger.error(f"list_tables error: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
def describe_table(table_name: str) -> str:
    """
    Shows the schema and columns of a specific table.

    Args:
        table_name: Name of the table e.g. emp or dept
    """
    try:
        conn = get_connection()
        query = f"""
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{table_name}'
            AND TABLE_SCHEMA = 'dbo'
            ORDER BY ORDINAL_POSITION
        """
        df = pd.read_sql(query, conn)
        conn.close()

        if df.empty:
            return f"Table '{table_name}' not found. Use list_tables to see available tables."
        return f"Schema of dbo.{table_name}:\n\n{df.to_string(index=False)}"
    except Exception as e:
        logger.error(f"describe_table error: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
def run_sql(query: str) -> str:
    """
    Runs a SQL SELECT query on the Fabric Lakehouse and returns results.
    Only SELECT statements are allowed for safety.

    Args:
        query: A valid T-SQL SELECT query e.g. SELECT * FROM dbo.emp
    """
    # Safety — only allow SELECT
    if not query.strip().upper().startswith("SELECT"):
        return "❌ Only SELECT queries are allowed for safety."

    try:
        conn = get_connection()
        df = pd.read_sql(query, conn)
        conn.close()

        if df.empty:
            return "✅ Query ran successfully but returned no results."

        return f"Rows returned: {len(df)}\n\n{df.to_string(index=False)}"
    except Exception as e:
        logger.error(f"run_sql error: {e}")
        return f"❌ SQL Error: {str(e)}"


@mcp.tool()
def ask_question(question: str) -> str:
    """
    Answers a plain English question about emp and dept data.
    Automatically generates the SQL, runs it on Fabric, and returns results.

    Args:
        question: Plain English question e.g.
                  'Who earns the most?'
                  'How many employees per department?'
                  'List all managers with their team size'
                  'Which department is in New York?'
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "❌ ANTHROPIC_API_KEY environment variable not set."

    prompt = f"""
{SCHEMA_CONTEXT}

User question: {question}

Generate a single T-SQL SELECT query to answer this question.
Return ONLY the SQL query, nothing else.
No explanations, no markdown, no code fences.
"""

    try:
        # Step 1 — generate SQL using Claude API
        response = req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )

        data = response.json()
        logger.info(f"Claude API response: {data}")

        # Check for API-level errors
        if "error" in data:
            return f"❌ Claude API Error: {data['error']['message']}"

        sql = data["content"][0]["text"].strip()
        logger.info(f"Generated SQL: {sql}")

        # Step 2 — run SQL on Fabric
        conn = get_connection()
        df = pd.read_sql(sql, conn)
        conn.close()

        if df.empty:
            return f"Question : {question}\nSQL Used  : {sql}\n\nNo results found."

        return (
            f"Question  : {question}\n"
            f"SQL Used  : {sql}\n\n"
            f"Results ({len(df)} rows):\n"
            f"{'=' * 40}\n"
            f"{df.to_string(index=False)}"
        )

    except Exception as e:
        logger.error(f"ask_question error: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
def sample_questions() -> str:
    """
    Returns a list of example questions you can ask about the emp and dept data.
    Use this to understand what kinds of questions are supported.
    """
    questions = [
        "Who earns the most salary?",
        "List all employees in department 20",
        "How many employees are in each department?",
        "What is the average salary per job title?",
        "Who are the managers and how many people report to them?",
        "Which department has the highest total salary bill?",
        "List employees hired before 1982",
        "Show me all SALESMANs with their commission",
        "Which employees earn more than their department average?",
        "Join emp and dept — show employee name, job, dept name and location",
    ]
    result = "Sample questions you can ask:\n\n"
    for i, q in enumerate(questions, 1):
        result += f"{i:2}. {q}\n"
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")