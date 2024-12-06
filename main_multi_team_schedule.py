import pandas as pd
import logging
from helpers.sleep_scoring import (
    multiple_games_in_short_timeframe,
    playing_at_high_altitude,
    night_spend_in_known_party_nightlife_city,
    calculate_running_sleep_debt,
    sleep_debt_penalty,
    game_time_is_played_during_handicapped_performance_hours,
    game_time_is_in_played_during_optimal_performance_hours,
    calculate_rest_time_between_games,
    calculate_sleep_score,
)
from helpers.clean_csv_multi_team import clean_data  # Import the cleaning function

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def apply_sleep_score_calculations(games_df):
    teams = games_df['Team'].unique()
    sleep_scores = pd.DataFrame()

    for team in teams:
        team_games = games_df[games_df['Team'] == team].copy()
        team_games.reset_index(drop=True, inplace=True)
        team_games = multiple_games_in_short_timeframe(team_games)
        team_games = playing_at_high_altitude(team_games)
        team_games = night_spend_in_known_party_nightlife_city(team_games)
        team_games = calculate_running_sleep_debt(team_games)
        team_games = sleep_debt_penalty(team_games)
        team_games = game_time_is_played_during_handicapped_performance_hours(team_games)
        team_games = game_time_is_in_played_during_optimal_performance_hours(team_games)
        team_games = calculate_rest_time_between_games(team_games)
        team_games = calculate_sleep_score(team_games)
        sleep_scores = pd.concat([sleep_scores, team_games], ignore_index=True)

    return sleep_scores

def merge_sleep_scores(games_df, sleep_scores):
    home_sleep_scores = sleep_scores[sleep_scores['Home_Game'] == True][
        ['Game_ID', 'Team', 'sleep_score']
    ].rename(columns={'Team': 'Home', 'sleep_score': 'Home_sleep_score'})

    visitor_sleep_scores = sleep_scores[sleep_scores['Home_Game'] == False][
        ['Game_ID', 'Team', 'sleep_score']
    ].rename(columns={'Team': 'Visitor', 'sleep_score': 'Visitor_sleep_score'})

    games_df = games_df.merge(home_sleep_scores, on=['Game_ID', 'Home'], how='left')
    games_df = games_df.merge(visitor_sleep_scores, on=['Game_ID', 'Visitor'], how='left')
    return games_df

def identify_specific_games(games_df):
    condition = (
        (
            ((games_df['Home_sleep_score'] >= 40) & (games_df['Home_sleep_score'] <= 60)) &
            (games_df['Visitor_sleep_score'] == 100)
        ) |
        (
            ((games_df['Visitor_sleep_score'] >= 40) & (games_df['Visitor_sleep_score'] <= 60)) &
            (games_df['Home_sleep_score'] == 100)
        )
    )
    specific_games = games_df[condition]
    return specific_games

def main():
    # Run the cleaning first
    success = clean_data()
    if not success:
        logging.error("Data cleaning failed. Exiting.")
        return

    # Now proceed since we have nba_games_updated.csv ready
    games_df = pd.read_csv('nba_games_updated.csv', parse_dates=["start_datetime_ET", "game_time_local_timezone"])
    
    games_df["LOG"] = pd.to_timedelta(games_df["LOG"])
    sleep_scores = apply_sleep_score_calculations(games_df)
    games_df = merge_sleep_scores(games_df, sleep_scores)
    specific_games = identify_specific_games(games_df)

    if not specific_games.empty:
        logging.info("Games where one team has a sleep score between 60-80 and the opponent has 100:")
        logging.info(specific_games[['Date', 'Start_ET', 'Visitor', 'Visitor_sleep_score', 'Home', 'Home_sleep_score']])
    else:
        logging.info("No games found matching the criteria.")

    specific_games.to_csv('specific_games.csv', index=False)
    logging.info("Specific games saved to 'specific_games.csv'.")

if __name__ == "__main__":
    main()