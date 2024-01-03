# Import packages
import os
import pathlib
from dash import Dash, html, dash_table, dcc, callback, Output, Input
import pandas as pd
import plotly.express as px
from ability_match import Build_Ability_match
from dash.dash_table.Format import Format, Scheme, Trim,Sign

# Create the ability of full match
api_url = 'json/Germany_3rd_liga/73699803_FT.json'

# Create the dropdown of log file
value_dropdown_list = [os.path.join('json',f) for f in os.listdir('json') if f.endswith('.json')]
key_dropdown_list = [pathlib.Path(f).stem for f in os.listdir('json') if f.endswith('.json')]


pickle_file_path = 'model/Germany_3rd_liga/rf_live_model.sav'
full_match_ability = Build_Ability_match(model_url=pickle_file_path, api_json_url=api_url)
home, away = full_match_ability.predict_full_match()

full_df = full_match_ability.full_match_df.drop(columns='per_expo_array')

# Initialize the app
app = Dash(__name__)

colors = {
    'background': '#111111',
    'text': '#7FDBFF'
}

name = pathlib.Path(api_url).stem

# App layout
app.layout = html.Div([
    html.H1(children=f'Ability Of Home and Away team in Match {name}',
            style={'textAlign': 'center'}),
    html.Label('Please choose Period'),
    dcc.Dropdown(options=['Period 1', 'Period 2'], value='Period 1', id='dropdown_period'),
    html.Div(id='update-table'),
    dcc.Graph(figure={}, id='home-ability-line'),
    dcc.Graph(figure={}, id='away-ability-line')
])


# # Create Plot for Home Team
@callback(
    Output(component_id='home-ability-line', component_property='figure'),
    Input(component_id='dropdown_period', component_property='value')
)
def update_home_ability(period):
    if period == 'Period 1':
        p = 1
    else:
        p = 2

    fig = px.line(data_frame=home[home['period'] == p],
                  x='second',
                  y='value',
                  color='type_ability',
                  hover_data=['home_p_in/de'],
                  labels={'home_p_in/de': 'Percentage'}
                  )

    fig.update_layout(yaxis_title='Ability',
                      xaxis_title='second',
                      title=f'Home ability vs Home expected Ability in Period {p}',
                      yaxis_tickformat=',.2f',
                      hovermode="x",
                      hoverlabel=dict(font=dict(color='white'))
                      )
    return fig


# Create Plot for Away Team
@callback(
    Output(component_id='away-ability-line', component_property='figure'),
    Input(component_id='dropdown_period', component_property='value')
)
def update_away_ability(period):
    if period == 'Period 1':
        p = 1
    else:
        p = 2

    fig_away = px.line(data_frame=away[away['period'] == p],
                       x='second',
                       y='value',
                       color='type_ability',
                       hover_data=['away_p_in/de'],
                       labels={'away_p_in/de': 'Percentage'},
                       color_discrete_map={
                           "away_ability": "#183D3D",
                           "away_exp_ability": "#E25E3E"
                       })

    fig_away.update_layout(yaxis_title='Ability',
                           xaxis_title='second',
                           title=f'Away ability vs Away expected Ability in Period {p}',
                           yaxis_tickformat=',.2f',
                           hovermode="x",
                           hoverlabel=dict(font=dict(color='white'))
                           )
    return fig_away

@callback(
    Output(component_id='update-table', component_property='children'),
    Input(component_id='dropdown_period', component_property='value')
)
def update_table(period):
    if period == 'Period 1':
        p = 1
    else:
        p = 2

    # Format column
    columns = [
        dict(id='period', name='Period', type='numeric',format=Format(precision=2, scheme=Scheme.decimal_integer)),
        dict(id='second', name='Second', type='numeric',format=Format(precision=2, scheme=Scheme.decimal_integer)),
        dict(id='field', name='Field', type='text'),
        dict(id='has_event', name='Event',type='text'),
        dict(id='update', name='Updated',type='text'),
        dict(id='home_p_in/de', name='Home Percent Increase', type='numeric', format=Format(precision=3, scheme=Scheme.fixed,sign=Sign.positive)),
        dict(id='away_p_in/de', name='Away Percent Increase', type='numeric', format=Format(precision=3, scheme=Scheme.fixed,sign=Sign.positive)),
        dict(id='home_ability', name='Home Ability', type='numeric', format=Format(precision=3, scheme=Scheme.fixed,sign=Sign.positive)),
        dict(id='home_exp_ability', name='Home Expected Ability', type='numeric', format=Format(precision=3, scheme=Scheme.fixed)),
        dict(id='away_ability', name='Away Ability', type='numeric', format=Format(precision=3, scheme=Scheme.fixed)),
        dict(id='away_exp_ability', name='Away Expected Ability', type='numeric', format=Format(precision=3, scheme=Scheme.fixed)),
    ]

    # Filter df
    df = full_df[full_df['period']==p]
    dtable = dash_table.DataTable(
        data=df.to_dict('records'),
        columns=columns,
        sort_action="native",
        page_size=14,  # we have less data in this example, so setting to 20
        fixed_rows={'headers': True},
        style_table={'height': '700px'}, # 'overflowY': 'auto'
        style_header={
            'backgroundColor': 'rgb(30, 30, 30)',
            'color': 'white'
        },
        style_data={
            'backgroundColor': 'rgb(50, 50, 50)',
            'color': 'white'
        },
        style_data_conditional=[
            {
                'if': {
                    'filter_query': '{away_p_in/de} > 0',
                    'column_id': 'away_p_in/de'
                },
                'backgroundColor': 'tomato',
                'color': 'white'
            },
            {
                'if': {
                    'filter_query': '{home_p_in/de} > 0',
                    'column_id': 'home_p_in/de'
                },
                'backgroundColor': 'blue',
                'color': 'white'
            }
        ]
    )
    return dtable


# Run the app
if __name__ == '__main__':
    app.run(debug=True)
