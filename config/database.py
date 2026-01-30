"""
Database configuration module.
"""
from .settings import DB_CONFIG


def get_connection_string():
    """Get MySQL connection string."""
    return (
        f"mysql+mysqlconnector://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )


def get_connection_params():
    """Get connection parameters as dict."""
    return DB_CONFIG.copy()
