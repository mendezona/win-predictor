# main.py

import helpers.clean_csv as clean_csv
import helpers.sleep_scoring as sleep_scoring
import os
import logging

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    try:
        logging.info("Starting CSV Cleaning...")
        clean_csv.main()

        # Validate 'nba_games_updated.csv' exists
        if not os.path.exists("nba_games_updated.csv"):
            logging.error("'nba_games_updated.csv' was not created.")
            return

        logging.info("CSV Cleaning Completed.\n")

        logging.info("Starting Sleep Scoring...")
        sleep_scoring.main()

        # Validate 'nba_games_scored.csv' exists
        if not os.path.exists("nba_games_scored.csv"):
            logging.error("'nba_games_scored.csv' was not created.")
            return

        logging.info("Sleep Scoring Completed.\n")
        logging.info("All processes completed successfully.")
    except Exception as e:
        logging.error(f"An error occurred in main.py: {e}")

if __name__ == "__main__":
    main()