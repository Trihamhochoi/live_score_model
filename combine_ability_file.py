import os
import pandas as pd
from pathlib import Path

# ability_urls = [os.path.join('ability_match/Germany_3rd_liga',f) for f in os.listdir('ability_match/Germany_3rd_liga') if 'FT' in f]
# ability_urls = [os.path.join('ability_match/Australia_league', f) for f in os.listdir('ability_match/Australia_league') if 'FT' in f]
# destination_dir = r"E:\PycharmProjects\Livescore_model\ability_match\Span_Primera_Ferderacion\log_data_27112023" #'ability_match/Span_Primera_Ferderacion'
destination_dir = 'ability_match/Australia_league'
ability_urls = [os.path.join(destination_dir, f) for f in os.listdir(destination_dir) if 'FT' in f]

full_match_ls = list()
for f in ability_urls:
    ability_df = pd.read_csv(f)
    # ability_df['match_id'] = n
    ability_df = ability_df.drop(columns='per_expo_array')
    arrange_col = ['match_id', 'period', 'second', 'field', 'has_event', 'update',
                   'home_p_in/de', 'away_p_in/de', 'home_perf_coef', 'away_perf_coef',
                   'home_ability', 'away_ability', 'home_exp_ability', 'away_exp_ability']
    ability_df = ability_df[arrange_col]
    full_match_ls.append(ability_df)

# Save File into 1 file csv
full_ability_df = pd.concat(full_match_ls, axis=0)

full_ability_df.to_csv(path_or_buf=os.path.join(destination_dir,'full_ab_Aus_matches.csv'),
                       index=False)

# full_ability_df.to_csv(path_or_buf='ability_match/Australia_league/full_abilities_2.csv',
#                        index=False)
# full_ability_df.to_csv(path_or_buf='ability_match/Germany_3rd_liga/ger_full_abilities_7.csv',
#                        index=False)
