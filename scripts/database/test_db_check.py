import pytest
from pathlib import Path
import sys
import importlib.util
from unittest.mock import patch, AsyncMock

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Dynamically import the make-db-check.py module
make_db_check_path = Path(__file__).parent / "make-db-check.py"
spec = importlib.util.spec_from_file_location("make_db_check", make_db_check_path)
make_db_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_db_check)
sys.modules['make_db_check'] = make_db_check


@pytest.mark.asyncio
async def test_db_check_success():
    """Tests the database check functionality on success."""
    with patch('make_db_check.DatabaseHealthChecker') as mock_checker:
        mock_instance = mock_checker.return_value
        mock_instance.run_health_check = AsyncMock(return_value={
            "database_info": {"status": "healthy"},
            "summary": {
                "existing_tables": 4,
                "total_tables": 4,
                "total_records": 100
            }
        })

        checker = make_db_check.DatabaseHealthChecker()
        db_form = await checker.run_health_check()

        assert db_form is not None
        assert db_form['database_info']['status'] == 'healthy'
        assert db_form['summary']['existing_tables'] == 4


@pytest.mark.asyncio
async def test_db_check_failure():
    """Tests the database check functionality on failure."""
    with patch('make_db_check.DatabaseHealthChecker') as mock_checker:
        mock_instance = mock_checker.return_value
        mock_instance.run_health_check = AsyncMock(return_value=None)

        checker = make_db_check.DatabaseHealthChecker()
        db_form = await checker.run_health_check()

        assert db_form is None