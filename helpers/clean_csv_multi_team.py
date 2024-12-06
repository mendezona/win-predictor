import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import logging
import sys

def clean_data():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Initialize geocoder and timezone finder
    geolocator = Nominatim(user_agent="nba_timezone_locator")
    tf = TimezoneFinder()

    # Define team location information (same as in clean_csv.py)
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

    try:
        team_info = team_locations.set_index("NBA Team").to_dict(orient="index")
    except KeyError as e:
        logging.error(f"Error setting index on 'NBA Team': {e}")
        logging.error("Available columns: %s", team_locations.columns.tolist())
        sys.exit(1)

    # Read the multi-team schedule CSV
    input_csv = "nba_games.csv"  # Adjust if necessary
    try:
        games_df = pd.read_csv(
            input_csv,
            sep=",",
            quotechar='"',
            skipinitialspace=True,
            engine="python",
            on_bad_lines="warn"
        )
    except FileNotFoundError:
        logging.error(f"Error: The file '{input_csv}' was not found.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An error occurred while reading '{input_csv}': {e}")
        sys.exit(1)

    # The raw format:
    # Date,Start (ET),Visitor/Neutral,PTS,Home/Neutral,PTS,,,Attend.,LOG,Arena,Notes
    # We'll rename columns to standard names
    # We'll drop extra columns that appear empty or just for "Box Score"
    # The columns after "PTS" for Home might be shifting. Let's define a stable indexing approach.
    # Expected columns (assuming no column name changes):
    # "Date", "Start (ET)", "Visitor/Neutral", "PTS", "Home/Neutral", "PTS.1", "Box Score", "", "Attend.", "LOG", "Arena", "Notes"
    # We can identify columns by name after reading.

    # Check columns
    logging.info("Original columns: %s", games_df.columns.tolist())

    # Let's rename and keep only what we need:
    # We'll keep: Date, Start (ET), Visitor/Neutral -> Visitor, PTS -> Visitor_PTS, Home/Neutral -> Home, PTS.1 -> Home_PTS, Attend., LOG, Arena
    # "Box Score" column and empty columns might appear as well. Let's see how columns align:
    # The provided sample: "Date", "Start (ET)", "Visitor/Neutral", "PTS", "Home/Neutral", "PTS.1", "Box Score", ""(empty?), "Attend.", "LOG", "Arena", "Notes"
    # We must identify these columns by position since the sample includes commas:
    # Let's drop "Box Score", empty columns or handle them carefully.

    # Identify columns by name:
    # We'll do a dictionary to rename only known columns and drop others:
    rename_map = {
        "Date": "Date",
        "Start (ET)": "Start_ET",
        "Visitor/Neutral": "Visitor",
        "PTS": "Visitor_PTS",
        "Home/Neutral": "Home",
        "PTS.1": "Home_PTS",
        "Attend.": "Attend",
        "LOG": "LOG",
        "Arena": "Arena",
        "Notes": "Notes"
    }

    # Rename columns we know, leave others out
    games_df.rename(columns=rename_map, inplace=True, errors="ignore")

    # Drop columns that are not in our rename_map and are not useful:
    keep_columns = list(rename_map.values())
    current_columns = games_df.columns.tolist()
    for col in current_columns:
        if col not in keep_columns:
            games_df.drop(columns=col, inplace=True)

    logging.info("Columns after renaming and dropping extras: %s", games_df.columns.tolist())

    # Parse 'Date' column to a uniform format
    # The date format looks like 'Sun Dec 1 2024'
    games_df['Date'] = pd.to_datetime(games_df['Date'], format='%a %b %d %Y', errors='coerce')

    # Parse 'Start_ET' similarly as in clean_csv.py
    # 'Start_ET' looks like '3:30p' - we need to convert to a time
    def parse_time(time_str):
        if pd.isna(time_str):
            return None
        time_str = str(time_str).strip().lower()
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

    games_df["parsed_time"] = games_df["Start_ET"].apply(parse_time)

    # Combine Date and parsed_time into a start_datetime_ET localized to ET
    def combine_date_time(row):
        if pd.isna(row["Date"]) or pd.isna(row["parsed_time"]):
            return pd.NaT
        return datetime(
            year=row["Date"].year,
            month=row["Date"].month,
            day=row["Date"].day,
            hour=row["parsed_time"].hour,
            minute=row["parsed_time"].minute,
            second=row["parsed_time"].second,
            tzinfo=ZoneInfo("America/New_York")  # localize to ET directly
        )

    games_df["start_datetime_ET"] = games_df.apply(combine_date_time, axis=1)

    # Each row currently represents one game with a Visitor and a Home team.
    # For sleep scoring, we need a row per team perspective.
    # We'll create a new DataFrame with two rows per game_id: one for the home perspective, one for the visitor perspective.

    # Assign Game_ID
    games_df['Game_ID'] = games_df.index  # each row is a unique game

    # We'll create a function to expand each row into two rows:
    # Home perspective:
    #   Team = Home
    #   Opponent = Visitor
    #   Team_PTS = Home_PTS
    #   Opponent_PTS = Visitor_PTS
    #   Home_Game = True
    #
    # Visitor perspective:
    #   Team = Visitor
    #   Opponent = Home
    #   Team_PTS = Visitor_PTS
    #   Opponent_PTS = Home_PTS
    #   Home_Game = False
    #
    # Keep Date, start_datetime_ET, etc. the same for both rows.

    records = []
    for _, row in games_df.iterrows():
        # Home perspective row
        home_dict = {
            "Game_ID": row["Game_ID"],
            "Date": row["Date"],
            "Start_ET": row["Start_ET"],
            "Team": row["Home"],
            "Opponent": row["Visitor"],
            "Team_PTS": row["Home_PTS"],
            "Opponent_PTS": row["Visitor_PTS"],
            "Home_Game": True,
            "Home": row["Home"],        # <-- Keep original Home team name
            "Visitor": row["Visitor"],  # <-- Keep original Visitor team name
            "Attend": row.get("Attend", None),
            "LOG": row.get("LOG", None),
            "Arena": row.get("Arena", None),
            "Notes": row.get("Notes", None),
            "start_datetime_ET": row["start_datetime_ET"]
        }

        # Visitor perspective row
        
        visitor_dict = {
            "Game_ID": row["Game_ID"],
            "Date": row["Date"],
            "Start_ET": row["Start_ET"],
            "Team": row["Visitor"],
            "Opponent": row["Home"],
            "Team_PTS": row["Visitor_PTS"],
            "Opponent_PTS": row["Home_PTS"],
            "Home_Game": False,
            "Home": row["Home"],         # same original Home team
            "Visitor": row["Visitor"],   # same original Visitor team
            "Attend": row.get("Attend", None),
            "LOG": row.get("LOG", None),
            "Arena": row.get("Arena", None),
            "Notes": row.get("Notes", None),
            "start_datetime_ET": row["start_datetime_ET"]
        }

        records.append(home_dict)
        records.append(visitor_dict)

    expanded_df = pd.DataFrame(records)

    # Now we have a row per team perspective.
    # Next, we add location and timezone info similarly to clean_csv.py
    # We'll define a function to get team location from team_info:
    def get_team_location(team_name):
        info = team_info.get(team_name.strip(), {})
        return pd.Series({
            "city": info.get("City", ""),
            "state": info.get("State/Province", ""),
            "country": info.get("Country", "")
        })

    location_info = expanded_df["Team"].apply(get_team_location)
    expanded_df = pd.concat([expanded_df, location_info], axis=1)

    # Check if some teams not found
    missing_teams = expanded_df[expanded_df["city"] == ""]
    if not missing_teams.empty:
        logging.warning("Some teams have missing location information:")
        logging.warning(missing_teams["Team"].unique())

    # Build location-timezone mapping as in clean_csv.py
    def get_timezone(city, state, country):
        if pd.isna(city) or city == "":
            return None
        location_str = f"{city}, {state}, {country}"
        try:
            loc = geolocator.geocode(location_str, timeout=10)
            if loc:
                tz_name = tf.timezone_at(lng=loc.longitude, lat=loc.latitude)
                return tz_name
            else:
                logging.warning(f"Could not geocode location: {location_str}")
                return None
        except Exception as e:
            logging.error(f"Error getting timezone for {city}, {state}, {country}: {e}")
            return None

    # Create mapping
    unique_locs = expanded_df[["city", "state", "country"]].drop_duplicates()
    loc_map = {}
    for _, lrow in unique_locs.iterrows():
        city, state, country = lrow["city"], lrow["state"], lrow["country"]
        tz = get_timezone(city, state, country)
        loc_map[(city, state, country)] = tz

    def lookup_timezone(row):
        return loc_map.get((row["city"], row["state"], row["country"]), None)

    expanded_df["timezone"] = expanded_df.apply(lookup_timezone, axis=1)

    # Convert ET time to local timezone
    def convert_to_local(row):
        if pd.isna(row["start_datetime_ET"]) or pd.isna(row["timezone"]) or row["timezone"] == "":
            return pd.NaT
        try:
            return row["start_datetime_ET"].astimezone(ZoneInfo(row["timezone"]))
        except Exception as e:
            logging.error(f"Timezone conversion failed for {row['timezone']}: {e}")
            return pd.NaT

    expanded_df["game_time_local_timezone"] = expanded_df.apply(convert_to_local, axis=1)

    # Compute win_loss from Team_PTS and Opponent_PTS
    expanded_df["win_loss"] = expanded_df.apply(lambda r: "W" if r["Team_PTS"] > r["Opponent_PTS"] else "L", axis=1)
    
    expanded_df["date_converted"] = expanded_df["Date"].dt.strftime("%Y-%m-%d")
    
    # If LOG missing, substitute with "2:00"
    expanded_df["LOG"] = expanded_df["LOG"].fillna("2:00")

    # Convert LOG to a timedelta
    expanded_df["LOG"] = pd.to_timedelta("0:" + expanded_df["LOG"])

    # Reorder columns similarly to clean_csv.py output
    final_columns = [
        "Game_ID",
        "Date",
        "date_converted",
        "Start_ET",
        "start_datetime_ET",
        "game_time_local_timezone",
        "Home_Game",
        "Team",
        "Opponent",
        "Team_PTS",
        "Opponent_PTS",
        "win_loss",
        "city",
        "state",
        "country",
        "timezone",
        "Attend",
        "LOG",
        "Arena",
        "Notes",
        "Home",
        "Visitor"
    ]

    # Ensure columns exist
    for col in final_columns:
        if col not in expanded_df.columns:
            expanded_df[col] = None  # add missing columns as needed

    expanded_df = expanded_df[final_columns]

    output_csv_path = "nba_games_updated.csv"
    try:
        expanded_df.to_csv(output_csv_path, index=False)
        logging.info(f"CSV file '{output_csv_path}' has been successfully created.")
    except Exception as e:
        logging.error(f"Error writing to '{output_csv_path}': {e}")
        sys.exit(1)
        
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    success = clean_data()
    if not success:
        logging.error("Data cleaning failed.")