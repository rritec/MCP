# Fabric SQL Agent - MCP Server

A Model Context Protocol (MCP) server that provides intelligent SQL query generation and execution against Microsoft Fabric's SQL Endpoint. This server enables AI assistants to interact with Fabric Lakehouse data through natural language questions.

## Overview

This MCP server acts as a bridge between language models (like Claude) and Microsoft Fabric SQL Endpoints. It exposes tools that allow AI assistants to:

- **List available tables** in your Fabric Lakehouse
- **Describe table schemas** and column details
- **Run SQL queries** directly on Fabric
- **Answer natural language questions** by automatically generating appropriate SQL queries using Claude AI
- **Browse sample questions** to understand capabilities

The server authenticates to Fabric using Azure interactive browser login, ensuring secure token-based access.

## Features

### Tools

#### `list_tables()`
Lists all available tables in the Fabric Lakehouse database.

**Usage:** Get an overview of what data is available before querying.

#### `describe_table(table_name: str)`
Shows the complete schema of a specific table, including column names, data types, and nullable flags.

**Args:**
- `table_name`: Name of the table (e.g., `emp` or `dept`)

#### `run_sql(query: str)`
Executes a T-SQL SELECT query directly on the Fabric Lakehouse.

**Args:**
- `query`: A valid T-SQL SELECT query

**Safety:** Only SELECT statements are allowed to prevent accidental data modifications.

**Example:**
```sql
SELECT ename, sal FROM dbo.emp WHERE deptno = 20
```

#### `ask_question(question: str)`
Answers plain English questions about your data by automatically generating and executing appropriate SQL queries.

**Args:**
- `question`: Natural language question about the data

**Features:**
- Uses Claude AI to generate SQL from natural language
- Automatically executes the generated query
- Returns both the question, generated SQL, and results

**Example Questions:**
- "Who earns the most salary?"
- "How many employees are in each department?"
- "Which department has the highest total salary bill?"

#### `sample_questions()`
Returns a list of example questions to help you get started with the natural language query feature.

## Schema

The server comes pre-configured to work with a sample employee/department database:

### `dbo.emp`
| Column | Type | Description |
|--------|------|-------------|
| empno | INT | Employee number (primary key) |
| ename | VARCHAR | Employee name |
| job | VARCHAR | Job title (CLERK, MANAGER, ANALYST, SALESMAN, PRESIDENT, CFO) |
| mgr | INT | Manager employee number |
| hiredate | DATETIME | Date hired |
| sal | FLOAT | Salary |
| comm | FLOAT | Commission |
| deptno | INT | Department number (foreign key) |

### `dbo.dept`
| Column | Type | Description |
|--------|------|-------------|
| deptno | INT | Department number (primary key) |
| dname | VARCHAR | Department name (ACCOUNTING, RESEARCH, SALES, OPERATIONS) |
| loc | VARCHAR | Location city |

**Relationship:** `emp.deptno = dept.deptno`

## Installation

### Requirements
- Python 3.13+
- Azure credentials (for Fabric authentication)
- ODBC Driver 18 for SQL Server

### Setup

1. **Clone the repository:**
```bash
git clone https://github.com/rritec/MCP.git
cd MCP
```

2. **Install dependencies:**
Using `uv` (fast Python package manager):
```bash
uv pip install -r requirements.txt
```

Or using pip:
```bash
pip install -r requirements.txt
```

3. **Required packages:**
- `mcp[cli]>=1.27.2` - Model Context Protocol framework
- `azure-identity>=1.25.3` - Azure authentication
- `pyodbc>=5.3.0` - SQL Server connectivity
- `pandas>=3.0.3` - Data manipulation and SQL query results
- `requests>=2.34.2` - HTTP requests (Claude API)
- `deltalake>=1.6.0` - Delta Lake support
- `pyarrow>=24.0.0` - Arrow for data processing
- `httpx>=0.28.1` - Modern HTTP client

## Configuration

Update the following values in `server.py`:

```python
# CONFIG — update these two values
SQL_ENDPOINT = "your-fabric-endpoint.datawarehouse.fabric.microsoft.com"
DATABASE = "your-database-name"
```

## Environment Variables

Set the following environment variable for natural language query support:

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

The `ask_question()` tool uses Claude API to generate SQL from natural language questions.

## Usage

### Running the Server

```bash
python server.py
```

The server starts in stdio mode and can be integrated with any MCP-compatible client.

### With Claude Desktop

Add this to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "fabric-sql-agent": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

### Example Queries

**List all tables:**
```
> list_tables()
Available tables in 'bronze':
TABLE_NAME    TABLE_TYPE
emp           BASE TABLE
dept          BASE TABLE
```

**Describe table schema:**
```
> describe_table("emp")
Schema of dbo.emp:
COLUMN_NAME  DATA_TYPE  CHARACTER_MAXIMUM_LENGTH  IS_NULLABLE
empno        int        NULL                      NO
ename        varchar    30                        NO
job          varchar    9                         NO
mgr          int        NULL                      YES
hiredate     datetime   NULL                      NO
sal          float      NULL                      NO
comm         float      NULL                      YES
deptno       int        NULL                      NO
```

**Run a SQL query:**
```
> run_sql("SELECT ename, sal FROM dbo.emp WHERE sal > 3000 ORDER BY sal DESC")
Rows returned: 5

ename    sal
KING     5000
SCOTT    3000
FORD     3000
JONES    2975
```

**Ask a natural language question:**
```
> ask_question("What is the average salary per job title?")
Question  : What is the average salary per job title?
SQL Used  : SELECT job, AVG(sal) as avg_salary FROM dbo.emp GROUP BY job ORDER BY avg_salary DESC

Results (6 rows):
========================================
job        avg_salary
PRESIDENT  5000
ANALYST    3000
MANAGER    2758.33
SALESMAN   1400
CLERK      1037.5
```

## Authentication Flow

The server uses Azure Interactive Browser Credential for authentication:

1. When a connection is needed, a browser window opens
2. User logs in with their Azure credentials
3. An access token is obtained for `https://database.windows.net`
4. The token is packaged in the format required by pyodbc
5. Connection is established to the Fabric SQL Endpoint

## Error Handling

- All tools include comprehensive error handling with logging to stderr
- SQL injection is prevented by parameterized queries (pandas `read_sql`)
- Only SELECT queries are allowed for safety
- API errors from Claude are clearly reported

## Logging

Logs are written to stderr (safe for MCP stdio transport):
```python
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
```

Check logs for debugging connection or query issues.

## Project Structure

```
MCP/
├── server.py                          # Main MCP server implementation
├── server_load_csv_to_delta_table.py # Utility for loading CSV to Delta tables
├── server_bkp.py                     # Backup of server code
├── main.py                           # Entry point
├── pyproject.toml                    # Project configuration
├── uv.lock                           # Dependency lock file
├── .python-version                   # Python version specification
├── .gitignore                        # Git ignore rules
└── README.md                         # This file
```

## Troubleshooting

### Connection Issues
- Verify `SQL_ENDPOINT` and `DATABASE` configuration
- Ensure ODBC Driver 18 for SQL Server is installed
- Check that Azure credentials have access to the Fabric resource

### Authentication Errors
- Make sure Azure authentication is interactive (browser login works)
- Verify ANTHROPIC_API_KEY is set for the `ask_question` feature

### Query Errors
- Use `list_tables()` to verify available tables
- Use `describe_table()` to check column names and data types
- Ensure only SELECT statements are used

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

[Add your license here if applicable]

## Support

For issues, questions, or feature requests, please create an issue on GitHub.

---

**Built with:**
- [Model Context Protocol](https://modelcontextprotocol.io/) (MCP)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [Microsoft Fabric](https://www.microsoft.com/en-us/fabric)
- [Claude AI](https://claude.ai/)
