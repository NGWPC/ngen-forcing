# Tests README

This directory contains tests for the NextGen Forcing BMI Engine.

The initial test data was generated using RTE to create a calibration realization
for gage 01123000, starting at time 2013-07-01 00:00:00, and running for 3 timesteps,
using RTE's run_suite.sh.  See RETRO_FORCING_CONFIG_FILE__AORC_CONUS.
## Test Structure

The test suite is organized into the following modules:

- **`esmf_regrid/`** - Tests for ESMF regridding functionality
- **`geomod/`** - Tests for geographic modeling components
- **`input_forcing/`** - Tests for input forcing data processing
- **`nextgen_forcings_ewts/`** - Tests for EWTS (Early Warning Tactical System) forcings
- **`test_utils.py`** - Shared test utilities and fixtures
- **`conftest.py`** - Pytest configuration and shared fixtures

## Prerequisites

### Required Dependencies

The test suite requires Python 3.11 or higher. Install the package with test dependencies:

```bash
# From the repository root directory
pip install -e ".[develop]"
```

Or install pytest directly:

```bash
pip install pytest
```

### Additional Requirements

Ensure all main package dependencies are installed. From the repository root:

```bash
pip install -e .
```

## Running Tests

### Run All Tests

```bash
Single processor: (cd src/ngen-forcing && pytest )
Multiple processors: ( cd src/ngen-forcing && mpirun -n 2 pytest )
```
### Run Specific Test Modules

Run tests for a specific module:

```bash
# ESMF regridding tests
Single processor: (cd src/ngen-forcing && pytest tests/esmf_regrid)
Multiple processors: ( cd src/ngen-forcing && mpirun -n 2 pytest tests/esmf_regrid)

# GeoMod tests
Single processor: (cd src/ngen-forcing && pytest tests/geomod)
Multiple processors: ( cd src/ngen-forcing && mpirun -n 2 pytest tests/geomod)

# Input forcing tests
Single processor: (cd src/ngen-forcing && pytest tests/input_forcing)
Multiple processors: ( cd src/ngen-forcing && mpirun -n 2 pytest tests/input_forcing)
```

Create new test output data (creates expected outputs for subsequent tests)
```bash
# ESMF regridding tests
Single processor: ( cd src/ngen-forcing && FORCING_PYTEST_WRITE_TEST_EXPECTED_DATA=true pytest tests/esmf_regrid)
Multiple processors: ( cd src/ngen-forcing && FORCING_PYTEST_WRITE_TEST_EXPECTED_DATA=true mpirun -n 2 pytest tests/esmf_regrid)

# GeoMod tests
Single processor: ( cd src/ngen-forcing && FORCING_PYTEST_WRITE_TEST_EXPECTED_DATA=true pytest tests/geomod)
Multiple processors: ( cd src/ngen-forcing && FORCING_PYTEST_WRITE_TEST_EXPECTED_DATA=true mpirun -n 2 pytest tests/geomod)

# Input forcing tests
Single processor: ( cd src/ngen-forcing && FORCING_PYTEST_WRITE_TEST_EXPECTED_DATA=true pytest tests/input_forcing)
Multiple processors: ( cd src/ngen-forcing && FORCING_PYTEST_WRITE_TEST_EXPECTED_DATA=true mpirun -n 2 pytest tests/input_forcing)
```
## Test Configuration

The test suite is configured via `pytest.ini` at the repository root:

- **Python path**: Set to repository root (`.`)
- **Logging**: Enabled with INFO level (DEBUG available by uncommenting)
- **Verbosity**: Full trace with verbose output (`-vv`)
- **Test paths**: Pre-configured to discover tests in `esmf_regrid`, `geomod`, and `input_forcing`


## Test Data

Test data is stored in the `test_data/` directory. Tests may reference files from this location for input data and expected results validation.

## Writing New Tests

When adding new tests:

1. Place test files in the appropriate subdirectory
2. Name test files with the `test_*.py` prefix
3. Name test functions with the `test_*` prefix
4. Use fixtures from `conftest.py` for common setup
5. Place test data files in `test_data/` with descriptive names

Example test structure:

```python
import pytest

def test_my_feature():
    """Test description."""
    # Arrange
    input_data = ...
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    assert result == expected_output
```
