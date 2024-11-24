# sleep_scoring.py

import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def multiple_games_in_short_timeframe(games_df):
    """
    Returns -40 if any of the following are true:
    - 4th game in six days
    - 3rd game in four days
    - 5th game in eight days
    - 2nd game in two days (back-to-back)
    Returns -60 if more than one condition is met.
    """
    penalties = []
    for idx in range(len(games_df)):
        penalty = 0
        conditions_met = 0
        current_game_date = pd.to_datetime(games_df.iloc[idx]["date_converted"])
        # Initialize counts
        games_in_2_days = 1
        games_in_4_days = 1
        games_in_6_days = 1
        games_in_8_days = 1
        for back_idx in range(idx - 1, -1, -1):
            prev_game_date = pd.to_datetime(games_df.iloc[back_idx]["date_converted"])
            delta_days = (current_game_date - prev_game_date).days
            if delta_days <= 1:
                games_in_2_days += 1
            if delta_days <= 3:
                games_in_4_days += 1
            if delta_days <= 5:
                games_in_6_days += 1
            if delta_days <= 7:
                games_in_8_days += 1
            else:
                break  # No need to check further back
        # Check conditions
        if games_in_2_days >= 2:
            conditions_met += 1
        if games_in_4_days >= 3:
            conditions_met += 1
        if games_in_6_days >= 4:
            conditions_met += 1
        if games_in_8_days >= 5:
            conditions_met += 1
        # Apply penalties
        if conditions_met > 1:
            penalty = -60
        elif conditions_met == 1:
            penalty = -40
        penalties.append(penalty)
    games_df["penalty_multiple_games"] = penalties
    return games_df

def real_time_hours_between_games(games_df):
    """
    Calculates the real-time hours between the end of the previous game and the start of the current game.
    """
    real_time_hours = [None]  # First game has no previous game
    for idx in range(1, len(games_df)):
        prev_end_time = games_df.iloc[idx - 1]["start_datetime_ET"] + games_df.iloc[idx - 1]["LOG"]
        current_start_time = games_df.iloc[idx]["start_datetime_ET"]
        delta = current_start_time - prev_end_time
        real_time_hours.append(delta.total_seconds() / 3600)
    games_df["hours_between_games"] = real_time_hours
    return games_df

def playing_at_high_altitude(games_df):
    """
    Returns -10 when the game city is Denver.
    """
    games_df["penalty_high_altitude"] = games_df["city"].apply(lambda x: -10 if x == "Denver" else 0)
    return games_df

def night_spend_in_known_party_nightlife_city(games_df):
    """
    Returns -10 when the location city is Los Angeles, Miami, Chicago, or Dallas.
    """
    party_cities = ["Los Angeles", "Miami", "Chicago", "Dallas"]
    games_df["penalty_nightlife_city"] = games_df["city"].apply(lambda x: -10 if x in party_cities else 0)
    return games_df

def calculate_running_sleep_debt(games_df):
    """
    Calculates the running sleep debt based on timezone differences and days spent at each location.
    """
    sleep_debt = [0]
    for idx in range(1, len(games_df)):
        try:
            prev_tz = ZoneInfo(games_df.iloc[idx - 1]["timezone"])
            curr_tz = ZoneInfo(games_df.iloc[idx]["timezone"])
            # Timezone offsets in hours
            prev_offset = datetime.now(prev_tz).utcoffset().total_seconds() / 3600
            curr_offset = datetime.now(curr_tz).utcoffset().total_seconds() / 3600
            tz_diff = curr_offset - prev_offset
            # Update sleep debt
            curr_sleep_debt = sleep_debt[-1] + tz_diff
            # Days at current location
            time_at_location = (
                games_df.iloc[idx]["start_datetime_ET"] - games_df.iloc[idx - 1]["start_datetime_ET"]
            ).total_seconds() / (24 * 3600)
            whole_days = int(time_at_location)
            # Reduce sleep debt towards zero
            if curr_sleep_debt > 0:
                curr_sleep_debt = max(curr_sleep_debt - whole_days, 0)
            elif curr_sleep_debt < 0:
                curr_sleep_debt = min(curr_sleep_debt + whole_days, 0)
            sleep_debt.append(curr_sleep_debt)
        except KeyError as e:
            logging.error(f"Missing timezone data at index {idx}: {e}")
            sleep_debt.append(sleep_debt[-1])  # Maintain previous sleep debt
        except Exception as e:
            logging.error(f"Error calculating sleep debt at index {idx}: {e}")
            sleep_debt.append(sleep_debt[-1])  # Maintain previous sleep debt
    games_df["running_sleep_debt"] = sleep_debt
    return games_df

def sleep_debt_penalty(games_df):
    """
    Returns -10 for each hour of sleep debt.
    """
    games_df["penalty_sleep_debt"] = games_df["running_sleep_debt"].apply(lambda x: -10 * abs(int(x)))
    return games_df

def game_time_is_played_during_handicapped_performance_hours(games_df):
    """
    Returns -20 when game time is played between 12:00 - 16:00 of the player's body clock.
    """
    penalties = []
    for idx in range(len(games_df)):
        game_time = games_df.iloc[idx]["start_datetime_ET"]
        sleep_debt_hours = games_df.iloc[idx]["running_sleep_debt"]
        if pd.isna(game_time):
            penalties.append(0)
            continue
        body_clock_time = game_time + timedelta(hours=sleep_debt_hours)
        body_clock_hour = body_clock_time.hour + body_clock_time.minute / 60
        if 12 <= body_clock_hour <= 16:
            penalties.append(-20)
        else:
            penalties.append(0)
    games_df["penalty_handicapped_hours"] = penalties
    return games_df

def game_time_is_in_played_during_optimal_performance_hours(games_df):
    """
    Returns +20 when game time is played between 16:01 - 20:00 of the player's body clock.
    """
    bonuses = []
    for idx in range(len(games_df)):
        game_time = games_df.iloc[idx]["start_datetime_ET"]
        sleep_debt_hours = games_df.iloc[idx]["running_sleep_debt"]
        if pd.isna(game_time):
            bonuses.append(0)
            continue
        body_clock_time = game_time + timedelta(hours=sleep_debt_hours)
        body_clock_hour = body_clock_time.hour + body_clock_time.minute / 60
        if 16.0167 <= body_clock_hour <= 20:
            bonuses.append(20)
        else:
            bonuses.append(0)
    games_df["bonus_optimal_hours"] = bonuses
    return games_df

def calculate_sleep_score(games_df):
    """
    Calculates the final sleep score by combining all penalties and bonuses.
    """
    games_df["sleep_score"] = 100
    games_df["sleep_score"] += games_df["penalty_multiple_games"]
    games_df["sleep_score"] += games_df["penalty_high_altitude"]
    games_df["sleep_score"] += games_df["penalty_nightlife_city"]
    games_df["sleep_score"] += games_df["penalty_sleep_debt"]
    games_df["sleep_score"] += games_df["penalty_handicapped_hours"]
    games_df["sleep_score"] += games_df["bonus_optimal_hours"]
    # Ensure the sleep score does not exceed 100
    games_df["sleep_score"] = games_df["sleep_score"].clip(upper=100)
    return games_df

def main():
    try:
        # Read the cleaned data
        games_df = pd.read_csv(
            "nba_games_updated.csv",
            parse_dates=["start_datetime_ET", "game_time_local_timezone"],
        )

        # Convert 'LOG' to timedelta
        games_df["LOG"] = pd.to_timedelta("0:" + games_df["LOG"].fillna("0:00"))

        # Check if 'win_loss' column exists
        if "win_loss" not in games_df.columns:
            logging.error("'win_loss' column is missing in 'nba_games_updated.csv'.")
            return

        # Apply the methods
        games_df = multiple_games_in_short_timeframe(games_df)
        games_df = real_time_hours_between_games(games_df)
        games_df = playing_at_high_altitude(games_df)
        games_df = night_spend_in_known_party_nightlife_city(games_df)
        games_df = calculate_running_sleep_debt(games_df)
        games_df = sleep_debt_penalty(games_df)
        games_df = game_time_is_played_during_handicapped_performance_hours(games_df)
        games_df = game_time_is_in_played_during_optimal_performance_hours(games_df)
        games_df = calculate_sleep_score(games_df)

        # Write the updated DataFrame to a new CSV file
        output_csv_path = "nba_games_scored.csv"
        games_df.to_csv(output_csv_path, index=False)
        logging.info(f"CSV file '{output_csv_path}' has been successfully created.")

        # Logging statements for analysis

        # Games with sleep score over 100
        over_100_games = games_df[games_df["sleep_score"] > 100]
        logging.info("Games with sleep score over 100:")
        if over_100_games.empty:
            logging.info("Empty DataFrame")
        else:
            logging.info(over_100_games[["G", "sleep_score"]])

        # Games with sleep score below 100
        below_100_games = games_df[games_df["sleep_score"] < 100]
        num_below_100 = len(below_100_games)
        losses_below_100 = len(below_100_games[below_100_games["win_loss"] == "L"])
        loss_ratio_below_100 = (
            (losses_below_100 / num_below_100 * 100) if num_below_100 > 0 else 0
        )
        logging.info(f"Number of games played below 100: {num_below_100}")
        logging.info(
            f"Losses below 100: {losses_below_100}, Wins below 100: {num_below_100 - losses_below_100}"
        )
        logging.info(f"Loss ratio below 100: {loss_ratio_below_100:.2f}%")
        logging.info("\n--------------------------------\n")

        # Separate into buckets of 20 in descending order
        sleep_score_buckets = [(80, 100), (60, 80), (40, 60), (20, 40), (0, 20)]
        for bucket_start, bucket_end in sleep_score_buckets:
            bucket_games = games_df[
                (games_df["sleep_score"] >= bucket_start)
                & (games_df["sleep_score"] < bucket_end)
            ]
            num_games = len(bucket_games)
            losses = len(bucket_games[bucket_games["win_loss"] == "L"])
            wins = num_games - losses
            loss_ratio = (losses / num_games * 100) if num_games > 0 else 0
            logging.info(f"Sleep score between {bucket_start} and {bucket_end}:")
            logging.info(
                f"Number of games: {num_games}, Losses: {losses}, Wins: {wins}, Loss ratio: {loss_ratio:.2f}%"
            )

        logging.info("Sleep Scoring Completed.")
    except Exception as e:
        logging.error(f"An error occurred in sleep_scoring.py: {e}")
        raise

if __name__ == "__main__":
    main()