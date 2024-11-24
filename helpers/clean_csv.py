# clean_csv.py

import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import logging

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Initialize geocoder and timezone finder
    geolocator = Nominatim(user_agent="nba_timezone_locator")
    tf = TimezoneFinder()

    # Define the team location information
    team_locations = pd.DataFrame({
        "NBA Team": [
            "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets",
            "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets",
            "Detroit Pistons", "Golden State Warriors", "Houston Rockets", "Indiana Pacers",
            "Los Angeles Clippers", "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat",
            "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans", "New York Knicks",
            "Oklahoma City Thunder", "Orlando Magic", "Philadelphia 76ers", "Phoenix Suns",
            "Portland Trail Blazers", "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors",
            "Utah Jazz", "Washington Wizards"
        ],
        "City": [
            "Atlanta", "Boston", "Brooklyn", "Charlotte", "Chicago", "Cleveland", "Dallas",
            "Denver", "Detroit", "San Francisco", "Houston", "Indianapolis", "Los Angeles",
            "Los Angeles", "Memphis", "Miami", "Milwaukee", "Minneapolis", "New Orleans",
            "New York", "Oklahoma City", "Orlando", "Philadelphia", "Phoenix", "Portland",
            "Sacramento", "San Antonio", "Toronto", "Salt Lake City", "Washington"
        ],
        "State/Province": [
            "Georgia", "Massachusetts", "New York", "North Carolina", "Illinois", "Ohio",
            "Texas", "Colorado", "Michigan", "California", "Texas", "Indiana", "California",
            "California", "Tennessee", "Florida", "Wisconsin", "Minnesota", "Louisiana",
            "New York", "Oklahoma", "Florida", "Pennsylvania", "Arizona", "Oregon", "California",
            "Texas", "Ontario", "Utah", "D.C."
        ],
        "Country": [
            "USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA",
            "USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA", "USA",
            "USA", "USA", "USA", "USA", "USA", "Canada", "USA", "USA"
        ]
    })

    # Debugging: Print the columns of team_locations
    logging.info("team_locations columns: %s", team_locations.columns.tolist())

    # Create a mapping from team names to location info
    try:
        team_info = team_locations.set_index("NBA Team").to_dict(orient="index")
    except KeyError as e:
        logging.error(f"Error setting index on 'NBA Team': {e}")
        logging.error("Available columns: %s", team_locations.columns.tolist())
        raise

    # Read the game data from CSV with proper handling of quotes and comma delimiter
    csv_file_path = "nba_games.csv"

    # Define the relevant columns to read (0-based indices)
    # 0: G, 1: Date, 2: Start_ET, 5: At, 6: Opponent, 9: Tm, 10: Opp, 11: W, 12: L, 13: Streak, 14: Attend., 15: LOG, 16: Notes
    usecols = [0, 1, 2, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16]

    # Read the CSV with usecols
    try:
        games_df = pd.read_csv(
            csv_file_path,
            sep=",",
            quotechar='"',
            skipinitialspace=True,
            engine="python",
            on_bad_lines="warn",
            usecols=usecols,
        )
    except FileNotFoundError:
        logging.error(
            f"Error: The file '{csv_file_path}' was not found. Please ensure it exists in the working directory."
        )
        raise
    except Exception as e:
        logging.error(f"An error occurred while reading '{csv_file_path}': {e}")
        raise

    # Debugging: Print the first few rows to verify correct reading
    logging.info("First few rows of games_df:")
    logging.info(games_df.head())

    # Assign meaningful column names
    games_df.columns = [
        "G",
        "Date",
        "Start_ET",
        "At",
        "Opponent",
        "Tm",
        "Opp",
        "W_total",
        "L_total",
        "Streak",
        "Attend",
        "LOG",
        "Notes",
    ]

    # Debugging: Print columns after renaming
    logging.info("Columns after renaming:")
    logging.info(games_df.columns.tolist())

    # Determine if each game is a home game based on the 'At' column
    # '@' indicates an away game, else home game
    games_df["home_game"] = games_df["At"].apply(
        lambda x: False if x == "@" else True
    )

    # Debugging: Check 'home_game' column
    logging.info("Home game determination:")
    logging.info(games_df[["G", "At", "home_game"]].head())

    # Define the home team's information
    team_city = "Minneapolis"
    team_state = "Minnesota"
    team_country = "USA"

    # Function to get location info based on game
    def get_location(row):
        if row["home_game"]:
            return pd.Series(
                {
                    "city": team_city,
                    "state": team_state,
                    "country": team_country
                }
            )
        else:
            opponent = str(row["Opponent"]).strip()
            info = team_info.get(opponent, {})
            if not info:
                logging.warning(f"Opponent '{opponent}' not found in team_info.")
            return pd.Series(
                {
                    "city": info.get("City", ""),
                    "state": info.get("State/Province", ""),
                    "country": info.get("Country", "")
                }
            )

    # Apply the function to each row
    location_info = games_df.apply(get_location, axis=1)
    games_df = pd.concat([games_df, location_info], axis=1)

    # Debugging: Check for missing location info
    missing_locations = games_df[games_df["city"] == ""]
    if not missing_locations.empty:
        logging.warning("Some games have missing location information:")
        logging.warning(missing_locations[["G", "Opponent"]])

    # Function to get timezone based on city, state, and country
    def get_timezone(city, state, country):
        try:
            # Construct the location string
            location_str = f"{city}, {state}, {country}"
            # Geocode the location
            location = geolocator.geocode(location_str, timeout=10)
            if location:
                # Get the timezone using latitude and longitude
                timezone_name = tf.timezone_at(lng=location.longitude, lat=location.latitude)
                return timezone_name
            else:
                logging.warning(f"Geocoding failed for location: {location_str}")
                return None
        except Exception as e:
            logging.error(f"Error getting timezone for {city}, {state}, {country}: {e}")
            return None

    # Build the location-timezone mapping
    def build_location_timezone_mapping(games_df):
        # Extract unique locations
        locations = games_df[['city', 'state', 'country']].drop_duplicates()
        # Initialize mapping
        location_timezone_mapping = {}
        for _, row in locations.iterrows():
            city = row['city']
            state = row['state']
            country = row['country']
            if pd.isna(city) or pd.isna(state) or pd.isna(country):
                continue
            timezone_name = get_timezone(city, state, country)
            if timezone_name:
                location_key = (city, state, country)
                location_timezone_mapping[location_key] = timezone_name
            else:
                logging.warning(f"Timezone not found for location: {city}, {state}, {country}")
        return location_timezone_mapping

    # Add the timezone to the games DataFrame
    def add_timezone_to_games_df(games_df, location_timezone_mapping):
        # Function to get timezone from mapping
        def lookup_timezone(row):
            city = row['city']
            state = row['state']
            country = row['country']
            location_key = (city, state, country)
            return location_timezone_mapping.get(location_key, None)
        # Add the 'timezone' column
        games_df['timezone'] = games_df.apply(lookup_timezone, axis=1)
        return games_df

    # Build the location-timezone mapping
    logging.info("Building location-timezone mapping...")
    location_timezone_mapping = build_location_timezone_mapping(games_df)
    logging.info("Location-timezone mapping completed.")

    # Add the timezone to the games DataFrame
    logging.info("Adding timezone information to games DataFrame...")
    games_df = add_timezone_to_games_df(games_df, location_timezone_mapping)
    logging.info("Timezone information added.")

    # Convert the 'Date' column to 'YYYY-MM-DD' format
    try:
        games_df["date_converted"] = pd.to_datetime(
            games_df["Date"], format="%a, %b %d, %Y"
        ).dt.strftime("%Y-%m-%d")
    except Exception as e:
        logging.error("Error converting 'Date' column: %s", e)
        # Attempt to parse without specifying format
        games_df["date_converted"] = pd.to_datetime(
            games_df["Date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")

    # Function to parse the 'Start_ET' time
    def parse_time(time_str):
        if pd.isna(time_str):
            return None
        time_str = str(time_str).strip().lower()
        # Handle 'p' and 'a' suffixes
        if time_str.endswith("p") and not time_str.endswith("pm"):
            time_str = time_str[:-1] + "pm"
        elif time_str.endswith("a") and not time_str.endswith("am"):
            time_str = time_str[:-1] + "am"
        try:
            return datetime.strptime(time_str, "%I:%M%p").time()
        except ValueError:
            try:
                return datetime.strptime(time_str, "%I%p").time()
            except ValueError:
                logging.warning(f"Time parsing failed for: '{time_str}'")
                return None

    # Parse the 'Start_ET' time
    games_df["start_time_ET"] = games_df["Start_ET"].apply(parse_time)

    # Handle any None values in 'start_time_ET'
    if games_df["start_time_ET"].isnull().any():
        logging.warning(
            "Some 'start_time_ET' values could not be parsed and are set to NaT."
        )

    # Combine 'date_converted' and 'start_time_ET' to create a datetime object
    def combine_date_time(row):
        if pd.isna(row["date_converted"]) or pd.isna(row["start_time_ET"]):
            return pd.NaT
        return datetime.strptime(row["date_converted"], "%Y-%m-%d").replace(
            hour=row["start_time_ET"].hour,
            minute=row["start_time_ET"].minute,
            second=row["start_time_ET"].second,
        )

    games_df["start_datetime_ET"] = games_df.apply(combine_date_time, axis=1)

    # Localize the datetime to Eastern Time
    try:
        games_df["start_datetime_ET"] = games_df[
            "start_datetime_ET"
        ].dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
    except Exception as e:
        logging.error(f"Error localizing 'start_datetime_ET' to 'America/New_York': {e}")
        games_df["start_datetime_ET"] = pd.NaT

    # Convert the Eastern Time to local game time
    def convert_to_local_time(row):
        if pd.isna(row["start_datetime_ET"]):
            return pd.NaT
        tz = row["timezone"]
        if pd.notna(tz) and tz != '':
            try:
                return row["start_datetime_ET"].astimezone(ZoneInfo(tz))
            except Exception as e:
                logging.error(f"Timezone conversion failed for '{tz}': {e}")
                return pd.NaT
        else:
            return pd.NaT

    games_df["game_time_local_timezone"] = games_df.apply(
        convert_to_local_time, axis=1
    )

    # Compute win/loss for each game
    games_df['win_loss'] = games_df.apply(
        lambda row: 'W' if row['Tm'] > row['Opp'] else 'L', axis=1
    )

    # Reorder columns for clarity
    final_columns = [
        "G",
        "Date",
        "date_converted",
        "Start_ET",
        "start_datetime_ET",
        "game_time_local_timezone",
        "home_game",
        "Opponent",
        "W_total",
        "L_total",
        "Streak",
        "win_loss",  # Added win_loss here
        "city",
        "state",
        "country",
        "timezone",
        "Attend",
        "LOG",
        "Notes",
    ]

    # Ensure all final columns exist before reordering
    existing_final_columns = [
        col for col in final_columns if col in games_df.columns
    ]
    missing_final_columns = set(final_columns) - set(existing_final_columns)
    if missing_final_columns:
        logging.warning(
            f"The following expected columns are missing and will not be included in the final output: {missing_final_columns}"
        )

    games_df = games_df[existing_final_columns]

    # Write the modified DataFrame to a new CSV file
    output_csv_path = "nba_games_updated.csv"
    try:
        games_df.to_csv(output_csv_path, index=False)
        logging.info(f"CSV file '{output_csv_path}' has been successfully created.")
    except Exception as e:
        logging.error(f"Error writing to '{output_csv_path}': {e}")
        raise

# Functions defined earlier (get_timezone, build_location_timezone_mapping, add_timezone_to_games_df)
# [Ensure these functions are included as per the code above.]

if __name__ == "__main__":
    main()