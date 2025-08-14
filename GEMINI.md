
# Gemini Code Assistant Context

## Project Overview

This project is a sophisticated Telegram message forwarding tool named "Telegram Forwarder". It allows users to forward messages from multiple Telegram chats (channels or groups) to other chats, with a rich set of features for filtering, modification, and enhancement. The tool is designed to be highly customizable and extensible.

The project is written in Python and utilizes the Telethon library for interacting with the Telegram API. It is containerized using Docker for easy deployment and management. The configuration is primarily handled through an environment file (`.env`) and several JSON/text files in the `config` directory.

The architecture is modular, with different components responsible for specific functionalities:

-   **Core Logic**: `main.py` and `message_listener.py` handle the main event loop and message listening.
-   **Filtering**: A chain of filters in the `filters` directory process messages based on various criteria like keywords, media type, etc.
-   **AI Integration**: The `ai` directory contains providers for various AI models (OpenAI, Claude, Gemini, etc.) to process messages for summarization, translation, or content filtering.
-   **Handlers**: The `handlers` directory manages user commands and button callbacks.
-   **RSS Service**: An integrated FastAPI application in the `rss` directory provides an RSS feed generation service from Telegram messages.
-   **Database**: The project uses a database (likely SQLite by default, as seen in `db_operations.py`) to store forwarding rules and other settings.

## Building and Running

The project is designed to be run with Docker and Docker Compose.

### Prerequisites

1.  **Telegram API Credentials**: `API_ID` and `API_HASH` from `my.telegram.org`.
2.  **Bot Token**: A `BOT_TOKEN` from `@BotFather`.
3.  **User ID**: Your Telegram `USER_ID` from `@userinfobot`.

### Configuration

1.  Create a `.env` file from the `.env.example`.
2.  Fill in the required environment variables, including the Telegram credentials and any AI provider API keys.

### Running the Application

1.  **Initial Run (Interactive Setup)**:
    ```bash
    docker-compose run -it telegram-forwarder
    ```
    This is required for the first run to enter your phone number, password, and 2FA code for the user session.

2.  **Daemon Mode**:
    After the initial setup, modify `docker-compose.yml` to set `stdin_open: false` and `tty: false`. Then, run the application in the background:
    ```bash
    docker-compose up -d
    ```

### Updating the Application

```bash
docker-compose down
docker-compose pull
docker-compose up -d
```

## Development Conventions

-   **Dependencies**: Python dependencies are managed in `requirements.txt`.
-   **Configuration**:
    -   Sensitive keys and environment-specific settings are in `.env`.
    -   Application-specific configurations, like AI models and filter settings, are in the `config` directory.
-   **AI Models**: Custom AI models can be added to `config/ai_models.json`.
-   **Modularity**: The code is organized into modules based on functionality (e.g., `filters`, `handlers`, `ai`).
-   **Filtering Logic**: The filtering process is a chain of responsibility pattern implemented in `filters/filter_chain.py`. Each filter in the chain processes the message and can modify it or stop further processing.
-   **Commands**: User-facing commands are defined in `handlers/command_handlers.py`.
-   **Logging**: The project uses a custom logging configuration from `utils/log_config.py`.

## Key Files

-   `main.py`: The main entry point of the application. It initializes the Telegram client and sets up the message listeners.
-   `message_listener.py`: Contains the core logic for handling incoming messages and passing them through the filter chain.
-   `docker-compose.yml`: Defines the Docker services for the main application and the optional RSS service.
-   `.env.example`: The template for the environment configuration file.
-   `requirements.txt`: Lists the Python dependencies for the project.
-   `filters/filter_chain.py`: Orchestrates the message filtering process.
-   `config/`: This directory is crucial for customizing the forwarder's behavior.
    -   `ai_models.json`: Defines the available AI models.
    -   `delay_times.txt`, `max_media_size.txt`, `media_extensions.txt`, `summary_times.txt`: Contain predefined values for various filter settings.
-   `rss/main.py`: The entry point for the FastAPI-based RSS service.
-   `PROJECT_DOCUMENTATION.md`: Provides a more in-depth technical documentation of the project.
