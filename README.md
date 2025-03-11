# PubMed Pharma Finder

This tool searches PubMed for articles matching a given query and identifies those with authors affiliated with pharmaceutical or biotech companies.

## Setup

1.  **Clone the repository (if applicable):**

    ```bash
    git clone https://github.com/SanjayReddy91/pubMedAPI.git
    cd pubMedAPI
    ```

2.  **Install Poetry:**

    If you don't have Poetry installed, install it using the following command:

    ```bash
    curl -sSL [https://install.python-poetry.org](https://install.python-poetry.org) | python3 -
    ```

    Make sure to add poetry to your path.

3.  **Install Dependencies:**

    Navigate to the project directory in your terminal and run:

    ```bash
    poetry install
    ```

    This will create a virtual environment and install all the necessary dependencies.

## Usage

You can run the script using the `get-papers-list` command provided by Poetry.

```bash
poetry run get-papers-list "your search query" --email your@email.com [options]