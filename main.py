import pandas as pd
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder
from geopy.geocoders import Nominatim

# Constants
NIGHTLIFE_CITIES = [
    'Los Angeles, California',
    'Miami, Florida',
    'Chicago, Illinois', 
    'Dallas, Texas',
    'Denver, Colorado'
]

# Sleep score thresholds
VERY_TIRED_THRESHOLD = 60
TIRED_THRESHOLD = 80
RESTED_THRESHOLD = 100

# Score adjustments
NIGHTLIFE_PENALTY = -10
TIMEZONE_HOUR_PENALTY = -20
REST_DAY_BONUS = 20
BACK_TO_BACK_PENALTY = -30
GAME_DENSITY_PENALTY = -20
CIRCADIAN_PENALTY = -80

# Initialize services
geolocator = Nominatim(user_agent="my_app")
tf = TimezoneFinder()


def get_timezone_diff(location, date_str):
    """Calculate timezone difference from UTC based on location and date."""
    try:
        date = datetime.strptime(date_str, "%a, %b %d, %Y")
        
        location_data = geolocator.geocode(location)
        if not location_data:
            return None
        
        timezone_str = tf.timezone_at(
            lat=location_data.latitude, 
            lng=location_data.longitude
        )
        
        if not timezone_str:
            return None
            
        timezone = pytz.timezone(timezone_str)
        utc_offset = timezone.utcoffset(date).total_seconds() / 3600
        return f"{utc_offset:+.1f}"
        
    except Exception as e:
        print(f"Error processing {location}: {str(e)}")
        return None


def calculate_timezone_impact(row, prev_row):
    """Calculate score impact from timezone changes."""
    if pd.isna(row['Timezone Difference (UTC)']) or \
       pd.isna(prev_row['Timezone Difference (UTC)']):
        return 0
        
    curr_tz = float(row['Timezone Difference (UTC)'])
    prev_tz = float(prev_row['Timezone Difference (UTC)'])
    tz_diff = abs(curr_tz - prev_tz)
    return tz_diff * TIMEZONE_HOUR_PENALTY


def calculate_density_penalties(df, current_idx, curr_date):
    """Calculate penalties for game density."""
    penalty = 0
    prev_games = df.iloc[max(0, current_idx-7):current_idx+1]['Date'].tolist()
    prev_games = [
        datetime.strptime(date, "%a, %b %d, %Y") 
        for date in prev_games
    ]
    prev_games.append(curr_date)
    
    # Check various windows
    windows = [
        (6, 4),  # 4 games in 6 days
        (4, 3),  # 3 games in 4 days
        (8, 5)   # 5 games in 8 days
    ]
    
    for days, threshold in windows:
        window = [
            d for d in prev_games 
            if (curr_date - d).days <= days - 1
        ]
        if len(window) >= threshold:
            penalty += GAME_DENSITY_PENALTY
            
    return penalty


def parse_game_time(time_str):
    """Parse game time string into datetime object."""
    formatted_time = time_str.upper().replace('P', 'PM').replace('A', 'AM')
    return datetime.strptime(formatted_time, "%I:%M%p")


def calculate_circadian_impact(row, prev_row):
    """Calculate circadian rhythm impact on sleep score."""
    try:
        curr_time = parse_game_time(row['Start (ET)'])
        prev_tz_offset = float(prev_row['Timezone Difference (UTC)'])
        curr_tz_offset = float(row['Timezone Difference (UTC)'])
        
        circadian_start = datetime.strptime("12:00PM", "%I:%M%p").time()
        circadian_end = datetime.strptime("4:00PM", "%I:%M%p").time()
        
        curr_hour_prev_tz = (
            curr_time.hour + 
            (prev_tz_offset - curr_tz_offset)
        ) % 24
        
        if (circadian_start.hour <= curr_hour_prev_tz <= circadian_end.hour):
            return CIRCADIAN_PENALTY
            
    except Exception as e:
        print(f"Error calculating circadian impact: {str(e)}")
    
    return 0


def calculate_sleep_score(row, prev_row, df, current_idx):
    """Calculate sleep score based on various factors."""
    if prev_row is None:
        return RESTED_THRESHOLD
    
    score = RESTED_THRESHOLD
    curr_date = datetime.strptime(row['Date'], "%a, %b %d, %Y")
    prev_date = datetime.strptime(prev_row['Date'], "%a, %b %d, %Y")
    
    # Apply nightlife penalty
    if row['Game Location'] in NIGHTLIFE_CITIES:
        score += NIGHTLIFE_PENALTY
    
    # Calculate timezone impact
    score += calculate_timezone_impact(row, prev_row)
    
    # Calculate rest days impact
    rest_days = (curr_date - prev_date).days - 1
    score += (rest_days * REST_DAY_BONUS)
    
    # Apply back-to-back penalty
    if (curr_date - prev_date).days == 1:
        score += BACK_TO_BACK_PENALTY
    
    # Apply game density penalties
    score += calculate_density_penalties(df, current_idx, curr_date)
    
    # Apply circadian rhythm penalties
    score += calculate_circadian_impact(row, prev_row)
    
    return max(0, min(100, score))


def analyze_fatigue_levels(df):
    """Analyze win percentages for different fatigue levels."""
    stats = {
        'very_tired': {'games': 0, 'wins': 0, 'losses': 0},
        'tired': {'games': 0, 'wins': 0, 'losses': 0},
        'slightly_tired': {'games': 0, 'wins': 0, 'losses': 0},
        'rested': {'games': 0, 'wins': 0, 'losses': 0}
    }
    
    for _, row in df.iterrows():
        category = get_fatigue_category(row['Sleep Score'])
        stats[category]['games'] += 1
        
        if row['Unnamed: 7'] == 'W':
            stats[category]['wins'] += 1
        elif row['Unnamed: 7'] == 'L':
            stats[category]['losses'] += 1
    
    print_fatigue_analysis(stats)


def get_fatigue_category(score):
    """Determine fatigue category based on sleep score."""
    if score < VERY_TIRED_THRESHOLD:
        return 'very_tired'
    elif score < TIRED_THRESHOLD:
        return 'tired'
    elif score < RESTED_THRESHOLD:
        return 'slightly_tired'
    return 'rested'


def print_fatigue_analysis(stats):
    """Print analysis results."""
    categories = {
        'very_tired': 'Very Tired Games (Sleep Score < 60)',
        'tired': 'Tired Games (Sleep Score 60-79)',
        'slightly_tired': 'Slightly Tired Games (Sleep Score 80-99)',
        'rested': 'Rested Games (Sleep Score = 100)'
    }
    
    print("\nWin Percentage Analysis:")
    for key, title in categories.items():
        stat = stats[key]
        win_pct = calculate_win_pct(stat)
        
        print(f"\n{title}:")
        print(f"Total Games: {stat['games']}")
        print(f"Wins: {stat['wins']}")
        print(f"Losses: {stat['losses']}")
        print(f"Win Percentage: {win_pct:.1f}%")


def calculate_win_pct(stat):
    """Calculate win percentage for given stats."""
    if stat['games'] == 0:
        return 0
    return (stat['wins'] / stat['games']) * 100


def main():
    """Main execution function."""
    # Load the CSV file
    file_path = 'Updated_Game_Schedule_with_Enhanced_Locations.csv'
    df = pd.read_csv(file_path, sep=';')
    
    # Calculate timezone differences
    df['Timezone Difference (UTC)'] = df.apply(
        lambda row: get_timezone_diff(row['Game Location'], row['Date']), 
        axis=1
    )
    
    # Calculate sleep scores
    sleep_scores = []
    prev_row = None
    
    for idx, row in df.iterrows():
        score = calculate_sleep_score(row, prev_row, df, idx)
        sleep_scores.append(score)
        prev_row = row
    
    df['Sleep Score'] = sleep_scores
    
    # Add nightlife impact column
    df['Nightlife Impact'] = df['Game Location'].apply(
        lambda x: 'Yes (-10)' if x in NIGHTLIFE_CITIES else 'No'
    )
    
    # Save updated data
    output_path = 'updated_schedule_with_timezones.csv'
    df.to_csv(output_path, index=False)
    print(f"Updated schedule saved to {output_path}")
    
    # Print debug information
    print("Shape of dataframe:", df.shape)
    print("\nFirst few rows of raw data:")
    print(df.head())
    print("\nColumn names:")
    print(df.columns.tolist())
    print("\nData types:")
    print(df.dtypes)
    
    # Analyze fatigue levels
    analyze_fatigue_levels(df)


if __name__ == "__main__":
    main()