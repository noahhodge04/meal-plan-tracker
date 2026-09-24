# Managing Virtual Environments and Requirements

## Virtual Environments

### Creating a virtual environment
1. Navigate to the `meal-plan-tracker` directory
2. Run `py -m venv .venv`  
This will create a new directory `.venv` containing the environment. The `.gitignore` file will automatically exclude this from git operations

### Activating a virtual environment
Run `.venv\Scripts\activate`  
You should see `(.venv)` at the start of your command line

## Requirements

### Installing requirements
Run `pip install -r requirements.txt`

### Updating requirements
Run `pip freeze > requirements.txt`