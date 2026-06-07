import sys
import logging
import requests
import pandas as pd
from io import StringIO
from mcp.server.fastmcp import FastMCP
from azure.identity import InteractiveBrowserCredential, ClientSecretCredential
from deltalake import write_deltalake

# Safe logging for stdio
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

mcp = FastMCP("fabric-lakehouse-loader")

# ── CONFIG ──────────────────────────────────────────────────
CSV_URL = "https://raw.githubusercontent.com/rritec/Microsoft-Fabric/refs/heads/main/Labdata/emp.csv"
# ────────────────────────────────────────────────────────────


@mcp.tool()
def preview_csv() -> str:
    """
    Fetches the emp.csv from GitHub and returns a preview
    of the data and schema before loading.
    """
    try:
        response = requests.get(CSV_URL, timeout=10)
        response.raise_for_status()

        df = pd.read_csv(StringIO(response.text))

        # Clean data
        df = _clean_dataframe(df)

        preview = f"""
CSV Preview from GitHub:
========================
Rows    : {len(df)}
Columns : {list(df.columns)}

Schema:
{df.dtypes.to_string()}

First 5 rows:
{df.head().to_string(index=False)}
        """
        return preview

    except Exception as e:
        return f"Error fetching CSV: {str(e)}"


@mcp.tool()
def load_csv_to_fabric(
    onelake_path: str,
    table_name: str = "emp",
    write_mode: str = "overwrite",
    tenant_id: str = "",
    client_id: str = "",
    client_secret: str = ""
) -> str:
    """
    Loads emp.csv from GitHub into Microsoft Fabric Lakehouse as a Delta table.

    Args:
        onelake_path: Full OneLake ABFSS path, e.g.
                      abfss://workspace@onelake.dfs.fabric.microsoft.com/lakehouse.Lakehouse/Tables/
        table_name:   Delta table name to create (default: emp)
        write_mode:   'overwrite' to replace or 'append' to add rows (default: overwrite)
        tenant_id:    Azure Tenant ID (for service principal auth, optional)
        client_id:    Azure Client ID / App ID (optional)
        client_secret: Azure Client Secret (optional)
    """
    try:
        # 1. Fetch CSV
        logger.info("Fetching CSV from GitHub...")
        response = requests.get(CSV_URL, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        logger.info(f"Fetched {len(df)} rows")

        # 2. Clean data
        df = _clean_dataframe(df)

        # 3. Build Delta table path
        if not onelake_path.endswith("/"):
            onelake_path += "/"
        delta_path = f"{onelake_path}{table_name}"

        # 4. Auth — Service Principal or Interactive Browser
        if tenant_id and client_id and client_secret:
            logger.info("Using Service Principal authentication...")
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        else:
            logger.info("Using Interactive Browser authentication...")
            credential = InteractiveBrowserCredential()

        # Get token for OneLake
        token = credential.get_token("https://storage.azure.com/.default")

        # 5. Storage options for OneLake
        storage_options = {
            "bearer_token": token.token,
            "use_fabric_endpoint": "true",
        }

        # 6. Write as Delta table
        logger.info(f"Writing Delta table to: {delta_path}")
        write_deltalake(
            table_or_uri=delta_path,
            data=df,
            mode=write_mode,
            storage_options=storage_options,
        )

        return f"""
✅ Success! Delta table created.
================================
Table     : {table_name}
Path      : {delta_path}
Rows      : {len(df)}
Columns   : {list(df.columns)}
Mode      : {write_mode}
        """

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
def get_table_info(
    onelake_path: str,
    table_name: str = "emp"
) -> str:
    """
    Returns info about an existing Delta table in Fabric Lakehouse.

    Args:
        onelake_path: Full OneLake ABFSS path
        table_name:   Delta table name to inspect
    """
    try:
        from deltalake import DeltaTable

        if not onelake_path.endswith("/"):
            onelake_path += "/"
        delta_path = f"{onelake_path}{table_name}"

        credential = InteractiveBrowserCredential()
        token = credential.get_token("https://storage.azure.com/.default")

        storage_options = {
            "bearer_token": token.token,
            "use_fabric_endpoint": "true",
        }

        dt = DeltaTable(delta_path, storage_options=storage_options)
        df = dt.to_pandas()

        return f"""
Delta Table Info:
=================
Table   : {table_name}
Version : {dt.version()}
Rows    : {len(df)}
Schema  : {df.dtypes.to_string()}

Sample:
{df.head(3).to_string(index=False)}
        """
    except Exception as e:
        return f"❌ Error: {str(e)}"


# ── HELPER ──────────────────────────────────────────────────
def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans the emp DataFrame — fixes types and nulls."""

    # Strip whitespace from column names
    df.columns = df.columns.str.strip().str.lower()

    # Fill numeric nulls with 0
    df["comm"] = pd.to_numeric(df["comm"], errors="coerce").fillna(0)
    df["mgr"]  = pd.to_numeric(df["mgr"],  errors="coerce").fillna(0).astype(int)
    df["sal"]  = pd.to_numeric(df["sal"],  errors="coerce").fillna(0)

    # Parse hiredate
    df["hiredate"] = pd.to_datetime(df["hiredate"], format="%d-%b-%y", errors="coerce")

    # Ensure correct types
    df["empno"]  = df["empno"].astype(int)
    df["deptno"] = df["deptno"].astype(int)

    return df
# ────────────────────────────────────────────────────────────


if __name__ == "__main__":
    mcp.run(transport="stdio")